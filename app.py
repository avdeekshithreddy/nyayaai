"""
NyayaAI — Indian Legal Scenario Analyzer
Main Streamlit Application
"""
import streamlit as st
import os
import sys

# ---------------------------------------------------------------------------
# Page configuration (MUST be the first Streamlit call)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="NyayaAI — Indian Legal Scenario Analyzer",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Load custom CSS
# ---------------------------------------------------------------------------
CSS_PATH = os.path.join(os.path.dirname(__file__), "assets", "style.css")
if os.path.exists(CSS_PATH):
    with open(CSS_PATH, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Imports (after page config)
# ---------------------------------------------------------------------------
from dotenv import load_dotenv

ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(ENV_PATH, override=True)

from database.db import init_db
from database.history import (
    create_conversation,
    save_message,
    get_conversations,
    get_messages,
    get_conversation,
    update_conversation_title,
    delete_conversation,
    delete_last_message,
    get_message_count,
)
from backend.chatbot import chatbot, ChatbotError
from backend.legal_analyzer import (
    analyze_scenario,
    generate_conversation_title,
    get_scenario_sources,
    is_api_configured,
    get_model_name,
)
from backend.retrieval import get_all_sources_metadata, search_sources
from utils.helpers import (
    sanitize_input,
    truncate_text,
    format_timestamp,
    validate_scenario,
    generate_report,
    extract_summary_from_messages,
    count_sources_in_response,
)

# ---------------------------------------------------------------------------
# Initialize database
# ---------------------------------------------------------------------------
init_db()

# ---------------------------------------------------------------------------
# Session state initialization
# ---------------------------------------------------------------------------
DEFAULTS = {
    "current_page": "home",
    "conversation_id": None,
    "messages": [],
    "processing": False,
    "response_language": "English",
    "response_detail": "Detailed",
    "last_sources": [],
    "delete_confirm": None,
    "active_prompt": None,
    "last_error": None,
    "last_error_code": None,
    "api_test_result": None,
}

for key, val in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = val


# ---------------------------------------------------------------------------
# Helper: switch page
# ---------------------------------------------------------------------------
def navigate(page: str):
    st.session_state.current_page = page


# ---------------------------------------------------------------------------
# Helper: start a new conversation
# ---------------------------------------------------------------------------
def new_conversation():
    st.session_state.conversation_id = None
    st.session_state.messages = []
    st.session_state.last_sources = []
    st.session_state.last_error = None
    st.session_state.active_prompt = None
    st.session_state.current_page = "home"


# ---------------------------------------------------------------------------
# Helper: load a conversation from DB
# ---------------------------------------------------------------------------
def load_conversation(conv_id: int):
    msgs = get_messages(conv_id)
    st.session_state.conversation_id = conv_id
    st.session_state.messages = [
        {"role": m["role"], "content": m["content"]} for m in msgs
    ]
    st.session_state.last_error = None
    st.session_state.active_prompt = None
    st.session_state.current_page = "home"
    # Retrieve sources for the last user message
    user_msgs = [m for m in msgs if m["role"] == "user"]
    if user_msgs:
        st.session_state.last_sources = get_scenario_sources(user_msgs[-1]["content"])


# ---------------------------------------------------------------------------
# Helper: render status badge
# ---------------------------------------------------------------------------
def render_status_badge():
    """Render an honest, accurate API status badge."""
    if not is_api_configured():
        return (
            '<div class="model-badge disconnected">'
            '<span class="dot"></span> API Key Missing'
            '</div>'
        )
    
    last_err = str(st.session_state.get("last_error", "")).lower()
    if "quota" in last_err or "credit" in last_err or "billing" in last_err:
        return (
            f'<div class="model-badge" style="background:rgba(245,158,11,0.12); border-color:rgba(245,158,11,0.35); color:#f59e0b;">'
            f'<span class="dot" style="background:#f59e0b; box-shadow:0 0 6px #f59e0b;"></span> Quota Exceeded'
            f'</div>'
        )
    
    if chatbot.last_api_success:
        return (
            f'<div class="model-badge">'
            f'<span class="dot"></span> Connected · {get_model_name()}'
            f'</div>'
        )

    # Configured but not yet confirmed by a live successful response
    return (
        f'<div class="model-badge" style="background:rgba(59,130,246,0.12); border-color:rgba(59,130,246,0.3); color:#60a5fa;">'
        f'<span class="dot" style="background:#3b82f6; box-shadow:0 0 6px #3b82f6;"></span> Configured · {get_model_name()}'
        f'</div>'
    )


# ---------------------------------------------------------------------------
# SIDEBAR — Navigation Rail
# ---------------------------------------------------------------------------
def render_sidebar():
    with st.sidebar:
        # Logo / branding
        st.markdown("# ⚖️ NyayaAI")
        st.markdown(
            '<p style="font-size:0.72rem; color:#5a6478; margin-top:-10px; letter-spacing:1px;">'
            "INDIAN LEGAL ANALYZER</p>",
            unsafe_allow_html=True,
        )
        st.markdown("---")

        # Navigation buttons
        if st.button("🏠  Home / Workspace", key="nav_home", use_container_width=True):
            navigate("home")

        if st.button("✨  New Legal Analysis", key="nav_new", use_container_width=True):
            new_conversation()
            st.rerun()

        if st.button("📂  Conversation History", key="nav_history", use_container_width=True):
            navigate("history")

        if st.button("📚  Legal Sources", key="nav_sources", use_container_width=True):
            navigate("sources")

        if st.button("⚙️  Settings", key="nav_settings", use_container_width=True):
            navigate("settings")

        st.markdown("---")

        # API status indicator
        st.markdown(render_status_badge(), unsafe_allow_html=True)

        # Session info
        st.markdown("---")
        conv_count = len(get_conversations())
        st.markdown(
            f'<p style="font-size:0.72rem; color:#5a6478;">'
            f"💾 {conv_count} saved conversation{'s' if conv_count != 1 else ''}</p>",
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# HEADER — Workspace top bar
# ---------------------------------------------------------------------------
def render_header():
    title = "NyayaAI Workspace"
    if st.session_state.conversation_id:
        conv = get_conversation(st.session_state.conversation_id)
        if conv:
            title = conv["title"]

    status_badge = render_status_badge()

    header_html = f"""
    <div class="workspace-header">
        <div class="header-left">
            <span class="brand-icon">⚖️</span>
            <div>
                <div class="brand-title">{title}</div>
                <div class="brand-subtitle">Indian Legal Scenario Analyzer</div>
            </div>
        </div>
        <div class="header-right">
            {status_badge}
        </div>
    </div>
    """
    st.markdown(header_html, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# WELCOME STATE — shown when no conversation is active
# ---------------------------------------------------------------------------
def render_welcome():
    st.markdown(
        """
    <div class="welcome-state">
        <div class="welcome-icon">⚖️</div>
        <div class="welcome-title">Welcome to NyayaAI</div>
        <div class="welcome-subtitle">
            Describe your legal situation to understand the relevant Indian laws and next steps.
        </div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    # Example questions
    st.markdown(
        '<p style="text-align:center; color:#5a6478; font-size:0.8rem; margin-bottom:0.5rem;">'
        "Try an example question:</p>",
        unsafe_allow_html=True,
    )

    examples = [
        {
            "icon": "🏠",
            "text": "My landlord is refusing to return my security deposit after I vacated the flat. What are my legal options?",
        },
        {
            "icon": "💼",
            "text": "My employer hasn't paid my salary for 3 months. What legal steps can I take?",
        },
        {
            "icon": "🛒",
            "text": "I bought a defective product online and the seller is refusing a refund. What consumer rights do I have?",
        },
        {
            "icon": "📱",
            "text": "Someone is posting defamatory content about me on social media. What legal remedies are available?",
        },
    ]

    cols = st.columns(2)
    for i, ex in enumerate(examples):
        with cols[i % 2]:
            if st.button(
                f"{ex['icon']}  {truncate_text(ex['text'], 80)}",
                key=f"example_{i}",
                use_container_width=True,
            ):
                st.session_state.active_prompt = ex["text"]
                st.session_state.last_error = None
                st.rerun()


# ---------------------------------------------------------------------------
# Helper: actionable hint for a Gemini error code
# ---------------------------------------------------------------------------
ERROR_HINTS = {
    "QUOTA_EXCEEDED": (
        "💡 **How to resolve:** Your Gemini free-tier quota for this model is used up (or the model has no free "
        "allowance on your project). Daily limits reset around midnight Pacific Time. You can wait, set a different "
        "free-tier model in `GEMINI_MODEL` in `.env`, or check your limits in [Google AI Studio](https://aistudio.google.com/). "
        "Then click **Retry Analysis**."
    ),
    "RATE_LIMIT": (
        "💡 **How to resolve:** Too many requests in a short time. Wait about a minute, then click **Retry Analysis**."
    ),
    "AUTH_FAILED": (
        "💡 **How to resolve:** Check `GEMINI_API_KEY` in your `.env` file, or create a new key at "
        "[Google AI Studio](https://aistudio.google.com/apikey). Changes take effect without restarting."
    ),
    "KEY_MISSING": (
        "💡 **How to resolve:** Add `GEMINI_API_KEY` to your `.env` file in the project root."
    ),
    "MODEL_MISSING": (
        "💡 **How to resolve:** Set `GEMINI_MODEL` in your `.env` file to a model ID available to your key "
        "(see the [model list](https://ai.google.dev/gemini-api/docs/models))."
    ),
    "MODEL_NOT_FOUND": (
        "💡 **How to resolve:** Change `GEMINI_MODEL` in your `.env` file to a currently available model ID "
        "(see the [model list](https://ai.google.dev/gemini-api/docs/models))."
    ),
    "SAFETY_BLOCKED": (
        "💡 **How to resolve:** Try rephrasing your scenario in neutral, factual terms, then retry."
    ),
    "CONNECTION_ERROR": (
        "💡 **How to resolve:** Check your internet connection, VPN or proxy, then click **Retry Analysis**."
    ),
    "SDK_MISSING": (
        "💡 **How to resolve:** Run `pip install -r requirements.txt` in your virtual environment and restart the app."
    ),
}


def render_error_hint(error_code):
    """Show an actionable hint for a known ChatbotError code (no-op for unknown codes)."""
    hint = ERROR_HINTS.get(error_code or "")
    if hint:
        st.info(hint)


# ---------------------------------------------------------------------------
# CORE EXECUTION: Scenario Analysis Runner
# ---------------------------------------------------------------------------
def execute_scenario_analysis(user_input: str) -> bool:
    """Execute analysis for user_input within the active assistant chat block.
    
    Returns True if response generation and saving succeeded.
    """
    user_input = sanitize_input(user_input)
    is_valid, error_msg = validate_scenario(user_input)
    if not is_valid:
        st.error(f"⚠️ {error_msg}")
        return False

    if not is_api_configured():
        st.error(
            "⚠️ **Gemini API Key Required**\n\n"
            "The Gemini API key is missing or not configured. "
            "Please add your key to `.env` in the project root: `GEMINI_API_KEY=your-key` "
            "(create one at https://aistudio.google.com/apikey)."
        )
        return False

    # Create conversation in DB if needed
    if st.session_state.conversation_id is None:
        conv_id = create_conversation()
        st.session_state.conversation_id = conv_id
    else:
        conv_id = st.session_state.conversation_id

    # Retrieve sources for display
    st.session_state.last_sources = get_scenario_sources(user_input)

    # Save user message to DB and state
    save_message(conv_id, "user", user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    # Prepare context & preferences
    history = [m for m in st.session_state.messages[:-1]]
    pref_note = ""
    if st.session_state.response_language != "English":
        pref_note += f" Please respond in {st.session_state.response_language}."
    if st.session_state.response_detail == "Concise":
        pref_note += " Keep your response concise and to the point."

    query_with_prefs = user_input + pref_note if pref_note else user_input

    # Execute streaming call
    st.session_state.processing = True
    full_response = ""

    try:
        response_generator = analyze_scenario(
            scenario=query_with_prefs,
            conversation_history=history,
            use_stream=True,
        )

        full_response = st.write_stream(response_generator)

        if full_response and full_response.strip():
            # Save assistant message to DB and state
            save_message(conv_id, "assistant", full_response)
            st.session_state.messages.append({"role": "assistant", "content": full_response})

            # Auto-generate title for first exchange
            if len(st.session_state.messages) == 2:
                try:
                    title = generate_conversation_title(user_input)
                    update_conversation_title(conv_id, title)
                except Exception:
                    update_conversation_title(conv_id, truncate_text(user_input, 50))

            st.session_state.last_error = None
            return True
        else:
            raise ChatbotError("Received an empty response from Gemini. Please try again.", error_code="EMPTY_RESPONSE")

    except ChatbotError as e:
        err_str = str(e)
        err_code = getattr(e, "error_code", None)
        st.session_state.last_error = err_str
        st.session_state.last_error_code = err_code
        st.error(f"⚠️ **Legal Scenario Analysis Failed**\n\n{err_str}")
        render_error_hint(err_code)
        return False

    except Exception as e:
        err_str = f"Unexpected error during legal analysis: {str(e)}"
        st.session_state.last_error = err_str
        st.session_state.last_error_code = None
        st.error(f"⚠️ {err_str}")
        return False

    finally:
        st.session_state.processing = False


# ---------------------------------------------------------------------------
# HOME PAGE — Minimal single-column workspace
# ---------------------------------------------------------------------------
def render_sources_expander():
    """Compact, collapsible list of the legal sources retrieved for the current question."""
    sources = st.session_state.last_sources
    if not (sources and st.session_state.messages):
        return
    with st.expander(f"📚 Sources referenced ({len(sources)})"):
        for s in sources[:6]:
            title = s.get("title", "Unknown")
            year = f" ({s['year']})" if s.get("year") else ""
            note = " — *replaced*" if s.get("status") == "replaced" else ""
            url = s.get("url", "")
            label = f"[{title}]({url})" if url else title
            st.markdown(f"- {label}{year}{note}")


def render_home():
    _, col_main, _ = st.columns([1, 3, 1])

    with col_main:
        # Top bar: title, New, Export
        conv_title = "Legal Analysis"
        if st.session_state.conversation_id:
            conv = get_conversation(st.session_state.conversation_id)
            if conv:
                conv_title = conv["title"]

        header_cols = st.columns([4, 1, 1])
        with header_cols[0]:
            st.markdown(f"#### {conv_title if st.session_state.messages else 'NyayaAI'}")
        with header_cols[1]:
            if st.button("✨ New", key="header_new", use_container_width=True):
                new_conversation()
                st.rerun()
        with header_cols[2]:
            if st.session_state.messages:
                report = generate_report(
                    conv_title,
                    st.session_state.messages,
                    st.session_state.last_sources,
                )
                st.download_button(
                    label="📥 Export",
                    data=report,
                    file_name=f"NyayaAI_Report_{conv_title[:30].replace(' ', '_')}.md",
                    mime="text/markdown",
                    key="export_report",
                    use_container_width=True,
                )

        # Welcome state if no messages and no active prompt
        if not st.session_state.messages and not st.session_state.active_prompt:
            render_welcome()
        else:
            # Render existing messages
            for msg in st.session_state.messages:
                avatar = "⚖️" if msg["role"] == "assistant" else "👤"
                with st.chat_message(msg["role"], avatar=avatar):
                    st.markdown(msg["content"])

            # Orphaned user message (failed prior attempt)
            if (
                st.session_state.messages
                and st.session_state.messages[-1]["role"] == "user"
                and not st.session_state.active_prompt
            ):
                with st.chat_message("assistant", avatar="⚖️"):
                    if st.session_state.last_error:
                        st.error(f"⚠️ **Previous Analysis Failed**\n\n{st.session_state.last_error}")
                        render_error_hint(st.session_state.get("last_error_code"))
                    else:
                        st.warning("⚠️ No AI response was generated for this scenario.")

                    c_r1, c_r2 = st.columns([1, 1])
                    with c_r1:
                        if st.button("🔄 Retry Analysis", key="retry_unanswered"):
                            unanswered_query = st.session_state.messages[-1]["content"]
                            st.session_state.messages.pop()
                            if st.session_state.conversation_id:
                                delete_last_message(st.session_state.conversation_id)
                            st.session_state.active_prompt = unanswered_query
                            st.session_state.last_error = None
                            st.rerun()
                    with c_r2:
                        if st.button("🗑️ Discard Question", key="discard_unanswered"):
                            st.session_state.messages.pop()
                            if st.session_state.conversation_id:
                                delete_last_message(st.session_state.conversation_id)
                            st.session_state.last_error = None
                            st.rerun()

        # Execute active prompt if submitted
        if st.session_state.active_prompt:
            prompt_to_run = st.session_state.active_prompt
            with st.chat_message("user", avatar="👤"):
                st.markdown(prompt_to_run)

            with st.chat_message("assistant", avatar="⚖️"):
                success = execute_scenario_analysis(prompt_to_run)
                st.session_state.active_prompt = None

                if success:
                    st.rerun()
                else:
                    if st.button("🔄 Retry", key="retry_active_failed"):
                        # Remove the failed user message from state and DB to retry cleanly
                        if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
                            st.session_state.messages.pop()
                            if st.session_state.conversation_id:
                                delete_last_message(st.session_state.conversation_id)
                        st.session_state.active_prompt = prompt_to_run
                        st.rerun()

        render_sources_expander()

        # Disclaimer
        st.markdown(
            '<div class="disclaimer-bar">'
            "⚠️ <strong>Disclaimer:</strong> NyayaAI provides general legal information "
            "for educational purposes. It is not a substitute for advice from a qualified "
            "Indian lawyer. Laws and outcomes depend on the facts and applicable law."
            "</div>",
            unsafe_allow_html=True,
        )

    # Chat input at bottom
    if prompt := st.chat_input("Describe your legal situation..."):
        st.session_state.active_prompt = prompt
        st.session_state.last_error = None
        st.rerun()


# ---------------------------------------------------------------------------
# HISTORY PAGE
# ---------------------------------------------------------------------------
def render_history():
    render_header()
    st.markdown("## 📂 Conversation History")
    st.markdown(
        '<p style="color:#8892a8; font-size:0.85rem;">'
        "Your saved legal analysis conversations (stored locally in SQLite)</p>",
        unsafe_allow_html=True,
    )

    conversations = get_conversations()

    if not conversations:
        st.markdown(
            '<div class="empty-state" style="padding:3rem;">'
            "No saved conversations yet. Start a new analysis to begin!</div>",
            unsafe_allow_html=True,
        )
        return

    for conv in conversations:
        with st.container():
            cols = st.columns([4, 1, 1])
            with cols[0]:
                btn_label = f"📄 {conv['title']}"
                if st.button(
                    btn_label,
                    key=f"load_{conv['id']}",
                    use_container_width=True,
                ):
                    load_conversation(conv["id"])
                    st.rerun()
                msg_count = get_message_count(conv["id"])
                st.markdown(
                    f'<span style="font-size:0.72rem; color:#5a6478;">'
                    f"{format_timestamp(conv['updated_at'])} · {msg_count} messages</span>",
                    unsafe_allow_html=True,
                )

            with cols[1]:
                st.markdown('<div style="padding-top:0.3rem;"></div>', unsafe_allow_html=True)
                if st.button("📥", key=f"export_{conv['id']}", help="Export conversation"):
                    msgs = get_messages(conv["id"])
                    messages_formatted = [
                        {"role": m["role"], "content": m["content"]} for m in msgs
                    ]
                    report = generate_report(conv["title"], messages_formatted)
                    st.download_button(
                        label="Download",
                        data=report,
                        file_name=f"NyayaAI_{conv['title'][:20].replace(' ', '_')}.md",
                        mime="text/markdown",
                        key=f"dl_{conv['id']}",
                    )

            with cols[2]:
                st.markdown('<div style="padding-top:0.3rem;"></div>', unsafe_allow_html=True)
                if st.session_state.delete_confirm == conv["id"]:
                    st.markdown(
                        '<span style="font-size:0.75rem; color:#ef4444;">Confirm?</span>',
                        unsafe_allow_html=True,
                    )
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button(
                            "Yes", key=f"confirm_del_{conv['id']}", type="primary"
                        ):
                            delete_conversation(conv["id"])
                            st.session_state.delete_confirm = None
                            if st.session_state.conversation_id == conv["id"]:
                                new_conversation()
                            st.rerun()
                    with c2:
                        if st.button("No", key=f"cancel_del_{conv['id']}"):
                            st.session_state.delete_confirm = None
                            st.rerun()
                else:
                    if st.button(
                        "🗑️",
                        key=f"del_{conv['id']}",
                        help="Delete conversation",
                    ):
                        st.session_state.delete_confirm = conv["id"]
                        st.rerun()

        st.markdown('<div class="connection-line"></div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# SOURCES PAGE
# ---------------------------------------------------------------------------
def render_sources():
    render_header()
    st.markdown("## 📚 Legal Sources Knowledge Base")
    st.markdown(
        '<p style="color:#8892a8; font-size:0.85rem;">'
        "Indian legal source metadata used for context retrieval. "
        "URLs point to official government sources where available.</p>",
        unsafe_allow_html=True,
    )

    sources = get_all_sources_metadata()

    if not sources:
        st.info("No legal sources configured.")
        return

    # Category filter
    categories = sorted(set(s.get("category", "") for s in sources))
    selected_cat = st.selectbox(
        "Filter by category",
        ["All"] + categories,
        key="source_filter",
    )

    filtered = (
        sources
        if selected_cat == "All"
        else [s for s in sources if s.get("category") == selected_cat]
    )

    # Render source cards
    cols = st.columns(2)
    for i, source in enumerate(filtered):
        with cols[i % 2]:
            status_class = "replaced" if source.get("status") == "replaced" else "active"
            status_label = "Replaced" if source.get("status") == "replaced" else "Active"
            replaced_note = ""
            if source.get("status") == "replaced" and source.get("replaced_by"):
                replaced_note = (
                    f'<div style="font-size:0.7rem; color:#f59e0b; margin-top:0.3rem;">'
                    f"⚠️ Replaced by: {source['replaced_by']}</div>"
                )
            url_link = ""
            if source.get("url"):
                url_link = (
                    f'<a href="{source["url"]}" target="_blank" '
                    f'style="font-size:0.72rem; color:#3b82f6;">🔗 Official Source</a>'
                )

            st.markdown(
                f"""
            <div class="source-card">
                <div class="source-title">{source.get('title', 'Unknown')}</div>
                <span class="source-category">{source.get('category', '')}</span>
                <span class="source-status {status_class}">{status_label}</span>
                <div class="source-desc">{source.get('description', '')}</div>
                <div class="source-meta">
                    📅 {source.get('year', 'N/A')} · 🏛️ {source.get('authority', 'N/A')}
                </div>
                {replaced_note}
                {url_link}
            </div>
            """,
                unsafe_allow_html=True,
            )
            st.markdown("")


# ---------------------------------------------------------------------------
# SETTINGS PAGE
# ---------------------------------------------------------------------------
def render_settings():
    render_header()
    st.markdown("## ⚙️ Settings & Diagnostics")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            '<div class="settings-section">'
            '<div class="settings-title">🤖 AI Configuration</div>'
            "</div>",
            unsafe_allow_html=True,
        )

        if is_api_configured():
            st.success(f"✅ Key Configured: `{chatbot.get_masked_key()}`")
            st.info(f"Target Model: **`{get_model_name()}`**")
            if not chatbot.is_model_configured:
                st.warning(
                    "⚠️ `GEMINI_MODEL` is missing or still a placeholder in `.env`. "
                    "Set it to a model ID available to your key before running an analysis."
                )

            test_cols = st.columns(2)
            with test_cols[0]:
                if st.button("🔍 Check Key & Model", key="test_api_btn", use_container_width=True):
                    with st.spinner("Checking Gemini key and model..."):
                        st.session_state.api_test_result = chatbot.test_connection()
            with test_cols[1]:
                if st.button(
                    "⚡ Live Generation Test",
                    key="test_api_live_btn",
                    use_container_width=True,
                    help="Sends one tiny request to Gemini (uses 1 request of your quota).",
                ):
                    with st.spinner("Sending a test request to Gemini..."):
                        st.session_state.api_test_result = chatbot.test_connection(live_check=True)

            if st.session_state.api_test_result:
                res = st.session_state.api_test_result
                if res["ok"]:
                    st.success(f"✅ **Connection Successful:** {res['message']}")
                else:
                    st.error(f"⚠️ **Connection Test Notice:**\n\n{res['message']}")
                    render_error_hint(res.get("status"))
        else:
            st.error("❌ Gemini API key not configured")
            st.markdown(
                """
            **Setup Instructions:**
            1. Get an API key from [Google AI Studio](https://aistudio.google.com/apikey)
            2. Open the `.env` file in your project root
            3. Add your key and a model ID:
            ```
            GEMINI_API_KEY=your-actual-key
            GEMINI_MODEL=a-model-id-from-the-pricing-page
            ```
            4. Changes take effect automatically without restarting!
            """
            )

        st.markdown(
            '<div class="settings-section">'
            '<div class="settings-title">🌐 Response Preferences</div>'
            "</div>",
            unsafe_allow_html=True,
        )

        st.session_state.response_language = st.selectbox(
            "Response Language",
            ["English", "Hindi", "Tamil", "Telugu", "Bengali", "Marathi", "Gujarati", "Kannada", "Malayalam"],
            index=["English", "Hindi", "Tamil", "Telugu", "Bengali", "Marathi", "Gujarati", "Kannada", "Malayalam"].index(
                st.session_state.response_language
            ),
            key="lang_select",
        )

        st.session_state.response_detail = st.radio(
            "Response Detail Level",
            ["Detailed", "Concise"],
            index=0 if st.session_state.response_detail == "Detailed" else 1,
            key="detail_select",
        )

    with col2:
        st.markdown(
            '<div class="settings-section">'
            '<div class="settings-title">💳 Billing & Quota Guidance</div>'
            "</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            """
        - 🆓 The Gemini API has a free tier for selected models, with per-minute and per-day request limits. Check [current pricing and free-tier models](https://ai.google.dev/gemini-api/docs/pricing).
        - 📊 If you see a quota or rate-limit error (HTTP 429), wait a minute, or wait for the daily reset (around midnight Pacific Time), then click Retry in chat.
        - 🔁 Each new conversation uses two requests (the analysis plus an auto-generated title).
        - 🔒 Your API key is loaded locally from `.env` and is never exposed in logs or reports.
        """
        )

        st.markdown(
            '<div class="settings-section">'
            '<div class="settings-title">💾 Data & Storage</div>'
            "</div>",
            unsafe_allow_html=True,
        )

        st.markdown(
            """
        - 📁 Conversations are stored locally in SQLite (`database/nyayaai.db`).
        - 🚫 No user data or prompts are shared with third parties except the Google Gemini API. On Google's free tier, submitted content may be used to improve Google products, so avoid entering confidential or identifying details.
        - 🗑️ You can manage or delete past analyses anytime in the History tab.
        """
        )

        st.markdown(
            '<div class="settings-section">'
            '<div class="settings-title">ℹ️ About NyayaAI</div>'
            "</div>",
            unsafe_allow_html=True,
        )

        st.markdown(
            """
        **NyayaAI — Indian Legal Scenario Analyzer**

        A college mini-project that uses AI to help users understand Indian legal situations.
        Built with Streamlit, Google Gemini, and SQLite.

        ⚠️ **Disclaimer:** This application provides general legal information for
        educational purposes only. It is not a substitute for advice from a qualified
        Indian lawyer. Laws and outcomes depend on the specific facts and applicable law.
        """
        )


# ---------------------------------------------------------------------------
# MAIN ROUTER
# ---------------------------------------------------------------------------
def main():
    render_sidebar()

    page = st.session_state.current_page

    if page == "home":
        render_home()
    elif page == "history":
        render_history()
    elif page == "sources":
        render_sources()
    elif page == "settings":
        render_settings()
    else:
        render_home()


if __name__ == "__main__":
    main()
