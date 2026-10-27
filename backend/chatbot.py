"""NyayaAI Chatbot - Google Gemini API integration for Indian legal analysis."""
import os
import re
import time
import logging
from typing import Generator, Optional, Dict, Any, List
from dotenv import load_dotenv

ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(ENV_PATH)

logger = logging.getLogger("nyayaai.chatbot")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# Gemini 3.x models can spend part of the output budget on internal "thinking",
# so this is intentionally larger than a plain-text answer would need.
MAX_OUTPUT_TOKENS = 8192
# google-genai expresses HTTP timeouts in milliseconds.
REQUEST_TIMEOUT_MS = 120_000


def scrub_secrets(text: Any) -> str:
    """Scrub sensitive credentials such as Gemini API keys and Bearer tokens from text."""
    if not text:
        return ""
    text_str = str(text)
    # Google API keys (AIza...)
    scrubbed = re.sub(r"AIza[0-9A-Za-z_\-]{20,}", "[REDACTED_API_KEY]", text_str)
    # Generic "sk-..." style keys (defensive)
    scrubbed = re.sub(r"sk-[a-zA-Z0-9_\-]{8,}", "[REDACTED_API_KEY]", scrubbed)
    # key=... query parameters and x-goog-api-key headers
    scrubbed = re.sub(r"(?i)(x-goog-api-key\"?\s*[:=]\s*\"?)[^\s\"',&]+", r"\1[REDACTED_API_KEY]", scrubbed)
    scrubbed = re.sub(r"(?i)([?&]key=)[^\s\"',&]+", r"\1[REDACTED_API_KEY]", scrubbed)
    # Bearer tokens in headers
    scrubbed = re.sub(r"Bearer\s+[a-zA-Z0-9_\-\.]+", "Bearer [REDACTED_TOKEN]", scrubbed)
    return scrubbed


def _short(text: str, limit: int = 600) -> str:
    """Trim very long provider error payloads for display."""
    text = text.strip()
    return text if len(text) <= limit else text[:limit] + "..."


def _is_placeholder(value: str) -> bool:
    """True if a .env value is empty or still an example placeholder."""
    v = (value or "").strip().lower()
    return (not v) or v.startswith("your_") or v.endswith("_here") or v == "your_actual_api_key"


def _load_sdk():
    """Import the google-genai SDK lazily so a missing package gives a clear UI error."""
    try:
        from google import genai
        from google.genai import types, errors
    except ImportError as e:
        raise ChatbotError(
            "The 'google-genai' package is not installed. "
            "Run: pip install -r requirements.txt (inside your virtual environment), then restart the app.",
            error_code="SDK_MISSING",
        ) from e
    return genai, types, errors


def _enum_name(value: Any) -> Optional[str]:
    """Return the readable name of an SDK enum (or None for unset/unspecified)."""
    if value is None:
        return None
    name = str(getattr(value, "name", None) or value)
    if "UNSPECIFIED" in name.upper():
        return None
    return name


class ChatbotError(Exception):
    """Custom exception for chatbot errors with user-friendly actionable message."""

    def __init__(self, message: str, error_code: Optional[str] = None):
        super().__init__(scrub_secrets(message))
        self.error_code = error_code


class NyayaChatbot:
    """Handles Gemini API interactions with robust error handling and minimal diagnostic logging."""

    def __init__(self):
        self._override_api_key: Optional[str] = None
        self._override_model: Optional[str] = None
        self._client = None
        self._cached_client_key: Optional[str] = None
        self.last_api_success: bool = False
        self.last_error_stage: Optional[str] = None

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    @property
    def api_key(self) -> str:
        """Get API key from override or freshly reloaded .env file."""
        if self._override_api_key is not None:
            return self._override_api_key
        if os.path.exists(ENV_PATH):
            load_dotenv(ENV_PATH, override=True)
        return (os.getenv("GEMINI_API_KEY", "") or "").strip()

    @api_key.setter
    def api_key(self, value: str):
        """Set override API key (useful for tests and dynamic configuration)."""
        self._override_api_key = value
        self._client = None
        self._cached_client_key = None

    @property
    def model(self) -> str:
        """Get model ID from override or freshly reloaded .env file (empty string if unset)."""
        if self._override_model is not None:
            raw = self._override_model
        else:
            if os.path.exists(ENV_PATH):
                load_dotenv(ENV_PATH, override=True)
            raw = os.getenv("GEMINI_MODEL", "") or ""
        raw = raw.strip()
        if raw.lower().startswith("models/"):
            raw = raw[len("models/"):]
        return raw

    @model.setter
    def model(self, value: str):
        """Set override model."""
        self._override_model = value

    @property
    def is_configured(self) -> bool:
        """Check if API key is configured (not empty or a placeholder)."""
        return not _is_placeholder(self.api_key)

    @property
    def is_model_configured(self) -> bool:
        """Check if a model ID is configured (not empty or a placeholder)."""
        return not _is_placeholder(self.model)

    def _require_model(self) -> str:
        """Return the configured model ID or raise an actionable error. Never substitutes a model."""
        if not self.is_model_configured:
            raise ChatbotError(
                "No Gemini model is configured. Set GEMINI_MODEL in your .env file to a model ID "
                "that is available to your key (see https://ai.google.dev/gemini-api/docs/models), then retry.",
                error_code="MODEL_MISSING",
            )
        return self.model

    @property
    def client(self):
        """Lazy-initialize or re-initialize Gemini client if key changes."""
        current_key = self.api_key
        if not self.is_configured:
            raise ChatbotError(
                "Gemini API key is not configured. Please add GEMINI_API_KEY to the .env file in the project root.",
                error_code="KEY_MISSING",
            )

        if self._client is None or self._cached_client_key != current_key:
            genai, types, _ = _load_sdk()
            try:
                self._client = genai.Client(
                    api_key=current_key,
                    http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_MS),
                )
                self._cached_client_key = current_key
                logger.info("Gemini client initialized successfully (model: %s)", self.model or "not set")
            except Exception as e:
                self.last_error_stage = "client_init"
                logger.error("Failed to initialize Gemini client: %s", scrub_secrets(e))
                raise ChatbotError(f"Failed to initialize Gemini client: {scrub_secrets(e)}") from e

        return self._client

    def get_masked_key(self) -> str:
        """Return a masked version of the API key for safe UI display."""
        key = self.api_key
        if not key or len(key) < 8 or not self.is_configured:
            return "Not configured"
        return f"{key[:4]}...{key[-4:]}"

    # ------------------------------------------------------------------
    # Error handling helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _is_network_error(e: Exception) -> bool:
        try:
            import httpx

            if isinstance(e, httpx.RequestError):
                return True
        except ImportError:
            pass
        return isinstance(e, (ConnectionError, TimeoutError))

    @staticmethod
    def _is_transient(e: Exception) -> bool:
        """Transient = temporary server (5xx) or network trouble. Quota/auth/bad-request are never transient."""
        try:
            from google.genai import errors

            if isinstance(e, errors.APIError):
                code = getattr(e, "code", None)
                return isinstance(code, int) and code in (500, 502, 503, 504)
        except ImportError:
            return False
        return NyayaChatbot._is_network_error(e)

    def _classify_error(self, e: Exception, stage: str) -> ChatbotError:
        """Classify Gemini SDK and general exceptions into user-friendly, actionable ChatbotErrors."""
        if isinstance(e, ChatbotError):
            return e

        self.last_error_stage = stage
        self.last_api_success = False
        err_msg = scrub_secrets(e)
        err_lower = err_msg.lower()

        try:
            _, _, errors = _load_sdk()
        except ChatbotError as sdk_err:
            return sdk_err

        if isinstance(e, errors.APIError):
            code = getattr(e, "code", None)
            status = str(getattr(e, "status", "") or "").upper()

            # --- Authentication / invalid key -------------------------------
            if (
                code == 401
                or status == "UNAUTHENTICATED"
                or "api key not valid" in err_lower
                or "api_key_invalid" in err_lower
                or "api key expired" in err_lower
                or "reported as leaked" in err_lower
            ):
                logger.error("[%s] Gemini authentication error (HTTP %s)", stage, code)
                return ChatbotError(
                    "Gemini authentication failed. Your API key is invalid, expired, revoked, or disabled. "
                    "Check GEMINI_API_KEY in your .env file or create a new key at https://aistudio.google.com/apikey.",
                    error_code="AUTH_FAILED",
                )

            # --- Rate limit / quota -----------------------------------------
            if code == 429 or status == "RESOURCE_EXHAUSTED":
                if "limit: 0" in err_lower:
                    logger.warning("[%s] Gemini 429: zero quota for this model on this project", stage)
                    return ChatbotError(
                        f"Your Gemini quota for model '{self.model}' is zero on this project, so it has no free-tier "
                        "allowance for this request. Set GEMINI_MODEL in .env to a model that is listed as free of charge "
                        "on https://ai.google.dev/gemini-api/docs/pricing, or enable billing in Google AI Studio.",
                        error_code="QUOTA_EXCEEDED",
                    )
                if any(t in err_lower for t in ("perday", "per day", "daily", "prepay", "credit", "billing")):
                    logger.warning("[%s] Gemini 429: daily/billing quota exhausted", stage)
                    return ChatbotError(
                        "Gemini quota exhausted: the daily free-tier request limit for this model has been reached "
                        "(or your prepaid balance is depleted). Daily limits reset around midnight Pacific Time. "
                        "You can wait, choose a different model in GEMINI_MODEL, or check your limits in Google AI Studio.",
                        error_code="QUOTA_EXCEEDED",
                    )
                if any(t in err_lower for t in ("perminute", "per minute")):
                    logger.warning("[%s] Gemini 429: per-minute rate limit", stage)
                    return ChatbotError(
                        "Gemini rate limit reached (too many requests or tokens per minute). "
                        "Please wait about a minute before submitting your question again.",
                        error_code="RATE_LIMIT",
                    )
                logger.warning("[%s] Gemini 429: unspecified rate limit / quota", stage)
                return ChatbotError(
                    "Gemini rate limit or free-tier quota reached. Please wait a minute and retry. "
                    "If it keeps happening, you may have used up the free quota for today.",
                    error_code="RATE_LIMIT",
                )

            # --- Model not found --------------------------------------------
            if code == 404 or status == "NOT_FOUND":
                logger.error("[%s] Gemini NOT_FOUND for model '%s'", stage, self.model)
                return ChatbotError(
                    f"The configured Gemini model '{self.model}' was not found, was retired, or does not support "
                    "content generation for your key. Set GEMINI_MODEL in your .env file to a currently available "
                    "model ID (see https://ai.google.dev/gemini-api/docs/models).",
                    error_code="MODEL_NOT_FOUND",
                )

            # --- Permission --------------------------------------------------
            if code == 403 or status == "PERMISSION_DENIED":
                logger.error("[%s] Gemini PERMISSION_DENIED", stage)
                return ChatbotError(
                    "Access was denied by the Gemini API. Your key may lack permission for this model or the "
                    f"Generative Language API may be disabled for its project. Details: {_short(err_msg, 300)}",
                    error_code="PERMISSION_DENIED",
                )

            # --- Server-side trouble ----------------------------------------
            if isinstance(code, int) and code >= 500:
                logger.error("[%s] Gemini server error (HTTP %s)", stage, code)
                return ChatbotError(
                    "The Gemini service is temporarily overloaded or unavailable. Please try again shortly.",
                    error_code="SERVER_ERROR",
                )

            # --- Bad request -------------------------------------------------
            if code == 400 or status in ("INVALID_ARGUMENT", "FAILED_PRECONDITION"):
                logger.error("[%s] Gemini BAD_REQUEST: %s", stage, _short(err_msg, 300))
                return ChatbotError(
                    f"Gemini rejected the request: {_short(err_msg)}",
                    error_code="BAD_REQUEST",
                )

            logger.error("[%s] Gemini APIError code=%s: %s", stage, code, _short(err_msg, 300))
            return ChatbotError(
                f"Gemini returned an API error (HTTP {code}): {_short(err_msg)}",
                error_code=f"HTTP_{code}",
            )

        if self._is_network_error(e):
            logger.error("[%s] Gemini connection/timeout error: %s", stage, type(e).__name__)
            return ChatbotError(
                "Unable to reach Google's Gemini servers (connection failed or timed out). "
                "Please check your internet connection, VPN, or network proxy and try again.",
                error_code="CONNECTION_ERROR",
            )

        logger.error("[%s] Unexpected exception: %s (%s)", stage, type(e).__name__, _short(err_msg, 300))
        return ChatbotError(
            f"An unexpected error occurred while communicating with the AI service: {_short(err_msg)}",
            error_code="UNEXPECTED_ERROR",
        )

    # ------------------------------------------------------------------
    # Request / response helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _build_contents(types, messages: List[dict]) -> list:
        """Convert OpenAI-style role/content messages into Gemini Content objects.

        - 'assistant' becomes Gemini's 'model' role; everything else is 'user'.
        - Empty messages are dropped.
        - Consecutive same-role messages (e.g. an unanswered question followed by a new one)
          are merged so the conversation always alternates cleanly.
        """
        turns: List[List[str]] = []  # [role, text]
        for msg in messages:
            text = (msg.get("content") or "").strip()
            if not text:
                continue
            role = "model" if msg.get("role") == "assistant" else "user"
            if turns and turns[-1][0] == role:
                turns[-1][1] += "\n\n" + text
            else:
                turns.append([role, text])
        return [types.Content(role=role, parts=[types.Part(text=text)]) for role, text in turns]

    @staticmethod
    def _extract_text(response: Any) -> str:
        """Safely get the visible text from a response or stream chunk."""
        try:
            return response.text or ""
        except Exception:
            return ""

    @staticmethod
    def _finish_reason(response: Any) -> Optional[str]:
        candidates = getattr(response, "candidates", None) or []
        if candidates:
            return _enum_name(getattr(candidates[0], "finish_reason", None))
        return None

    @staticmethod
    def _block_reason(response: Any) -> Optional[str]:
        feedback = getattr(response, "prompt_feedback", None)
        return _enum_name(getattr(feedback, "block_reason", None)) if feedback else None

    def _empty_response_error(self, block_reason: Optional[str], finish_reason: Optional[str]) -> ChatbotError:
        """Build an honest error for a response that contained no usable text."""
        self.last_error_stage = "empty_response"
        if block_reason:
            logger.warning("Gemini blocked the prompt (block_reason=%s)", block_reason)
            return ChatbotError(
                f"Gemini blocked this request before answering (reason: {block_reason}). "
                "Try rephrasing the scenario in more neutral, factual terms.",
                error_code="SAFETY_BLOCKED",
            )
        if finish_reason and finish_reason not in ("STOP", "MAX_TOKENS"):
            logger.warning("Gemini returned no text (finish_reason=%s)", finish_reason)
            return ChatbotError(
                f"Gemini returned no answer (finish reason: {finish_reason}). Its safety or content filters may have "
                "stopped the response. Try rephrasing the scenario.",
                error_code="SAFETY_BLOCKED",
            )
        if finish_reason == "MAX_TOKENS":
            logger.warning("Gemini hit the output token limit before producing visible text")
            return ChatbotError(
                "Gemini used its whole output budget before producing a visible answer. Please retry, "
                "or ask a shorter question.",
                error_code="EMPTY_RESPONSE",
            )
        logger.warning("Gemini returned an empty response (finish_reason=%s)", finish_reason)
        return ChatbotError(
            "Gemini returned an empty response. Please try again.",
            error_code="EMPTY_RESPONSE",
        )

    def _build_config(self, types, system_prompt: str, temperature: float, max_output_tokens: int = MAX_OUTPUT_TOKENS):
        return types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------
    def test_connection(self, live_check: bool = False) -> Dict[str, Any]:
        """Verify credentials and model honestly.

        Default (live_check=False): looks up the configured model's metadata. This proves the key is accepted
        and the model exists, but does NOT prove that generation quota is available.
        live_check=True: also sends one tiny generation request (uses 1 request of your quota).
        """
        if not self.is_configured:
            return {
                "ok": False,
                "status": "unconfigured",
                "message": "Gemini API key is missing or still set to the placeholder in .env.",
            }
        if not self.is_model_configured:
            return {
                "ok": False,
                "status": "MODEL_MISSING",
                "message": "GEMINI_MODEL is missing or still set to the placeholder in .env.",
            }

        try:
            _, types, _ = _load_sdk()
            model_name = self.model
            logger.info("Running diagnostic connection check (model lookup%s)...", " + live generation" if live_check else "")
            info = self.client.models.get(model=model_name)

            actions = getattr(info, "supported_actions", None)
            if actions and "generateContent" not in actions:
                return {
                    "ok": False,
                    "status": "MODEL_UNSUPPORTED",
                    "model": model_name,
                    "model_available": True,
                    "message": f"Model '{model_name}' exists but does not support text generation (generateContent). "
                    "Choose a different GEMINI_MODEL.",
                }

            if not live_check:
                return {
                    "ok": True,
                    "status": "connected",
                    "model": model_name,
                    "model_available": True,
                    "message": f"API key accepted and model '{model_name}' found. This check does not use generation "
                    "quota, so rate limits and free-tier quota are only confirmed by a live test or a real analysis.",
                }

            response = self.client.models.generate_content(
                model=model_name,
                contents="Reply with the single word: OK",
                config=types.GenerateContentConfig(temperature=0, max_output_tokens=256),
            )
            self.last_api_success = True
            text = self._extract_text(response).strip()
            return {
                "ok": True,
                "status": "connected",
                "model": model_name,
                "model_available": True,
                "message": f"Live test succeeded: Gemini model '{model_name}' accepted a generation request"
                + (f" and replied '{text[:40]}'." if text else " (the reply text was empty, but the request itself succeeded)."),
            }
        except Exception as e:
            classified = self._classify_error(e, stage="test_connection")
            return {
                "ok": False,
                "status": classified.error_code or "error",
                "message": str(classified),
            }

    # ------------------------------------------------------------------
    # Chat
    # ------------------------------------------------------------------
    def chat(
        self,
        messages: list[dict],
        system_prompt: str,
        temperature: float = 0.3,
        max_retries: int = 1,
    ) -> str:
        """Send a synchronous chat request to Gemini with safe retry logic for transient errors only."""
        model_name = self._require_model()
        _, types, _ = _load_sdk()
        contents = self._build_contents(types, messages)
        if not contents:
            raise ChatbotError("There is no message content to send to Gemini.", error_code="EMPTY_INPUT")

        config = self._build_config(types, system_prompt, temperature)
        logger.info("Executing chat completion (model: %s, turns: %d)", model_name, len(contents))

        for attempt in range(max_retries + 1):
            try:
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=config,
                )
            except ChatbotError:
                raise
            except Exception as e:
                transient = self._is_transient(e)
                if transient and attempt < max_retries:
                    wait_time = 2 ** attempt
                    logger.warning(
                        "Transient error on attempt %d/%d; retrying in %ds: %s",
                        attempt + 1, max_retries + 1, wait_time, scrub_secrets(e),
                    )
                    time.sleep(wait_time)
                    continue
                stage = "chat_transient_exhausted" if transient else "chat_request"
                raise self._classify_error(e, stage=stage) from e

            text = self._extract_text(response)
            if text.strip():
                self.last_api_success = True
                if self._finish_reason(response) == "MAX_TOKENS":
                    logger.warning("Response was cut off at the output token limit")
                logger.info("Chat completion completed successfully (response length: %d)", len(text))
                return text

            raise self._empty_response_error(self._block_reason(response), self._finish_reason(response))

        # Defensive: loop always returns or raises above.
        raise ChatbotError("Gemini request failed after retries.", error_code="UNEXPECTED_ERROR")

    def chat_stream(
        self,
        messages: list[dict],
        system_prompt: str,
        temperature: float = 0.3,
        max_retries: int = 1,
    ) -> Generator[str, None, None]:
        """Send a streaming chat request to Gemini, yielding text chunks safely."""
        model_name = self._require_model()
        _, types, _ = _load_sdk()
        contents = self._build_contents(types, messages)
        if not contents:
            raise ChatbotError("There is no message content to send to Gemini.", error_code="EMPTY_INPUT")

        config = self._build_config(types, system_prompt, temperature)
        logger.info("Initiating streaming chat completion (model: %s, turns: %d)", model_name, len(contents))

        attempt = 0
        while True:
            chunk_count = 0
            block_reason: Optional[str] = None
            finish_reason: Optional[str] = None
            try:
                stream = self.client.models.generate_content_stream(
                    model=model_name,
                    contents=contents,
                    config=config,
                )
                for chunk in stream:
                    block_reason = self._block_reason(chunk) or block_reason
                    finish_reason = self._finish_reason(chunk) or finish_reason
                    text = self._extract_text(chunk)
                    if text:
                        chunk_count += 1
                        yield text
            except ChatbotError:
                raise
            except Exception as e:
                # Only retry if nothing has been shown to the user yet (avoids duplicated text).
                if chunk_count == 0 and attempt < max_retries and self._is_transient(e):
                    wait_time = 2 ** attempt
                    attempt += 1
                    logger.warning("Transient stream error; retrying in %ds: %s", wait_time, scrub_secrets(e))
                    time.sleep(wait_time)
                    continue
                stage = "stream_iteration" if chunk_count else "stream_initialization"
                raise self._classify_error(e, stage=stage) from e
            break

        if chunk_count == 0:
            raise self._empty_response_error(block_reason, finish_reason)

        self.last_api_success = True
        if finish_reason == "MAX_TOKENS":
            logger.warning("Streamed response was cut off at the output token limit")
        logger.info("Streaming completed successfully (chunks received: %d)", chunk_count)

    def generate_title(self, first_message: str) -> str:
        """Generate a short title for a conversation based on the first message."""
        from backend.prompts import get_title_prompt

        try:
            response = self.chat(
                messages=[{"role": "user", "content": get_title_prompt(first_message)}],
                system_prompt="You generate very short titles (max 6 words). Return only the title text, nothing else.",
                temperature=0.5,
                max_retries=0,
            )
            title = response.strip().strip('"').strip("'")[:60]
            return title if title else "Legal Analysis"
        except Exception as e:
            logger.info("Title generation skipped due to API error: %s; using fallback title", scrub_secrets(e))
            return first_message[:50].strip() + ("..." if len(first_message) > 50 else "")


# Singleton instance
chatbot = NyayaChatbot()
