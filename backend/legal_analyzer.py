"""NyayaAI Legal scenario analysis engine."""
import logging
from typing import Generator
from backend.chatbot import chatbot, ChatbotError
from backend.prompts import get_system_prompt, get_analysis_prompt
from backend.retrieval import get_relevant_context

logger = logging.getLogger("nyayaai.legal_analyzer")


def analyze_scenario(
    scenario: str,
    conversation_history: list[dict],
    use_stream: bool = True,
) -> str | Generator[str, None, None]:
    """Analyze a legal scenario using AI with retrieved context.
    
    Args:
        scenario: The user's legal question or scenario.
        conversation_history: Previous messages in the conversation.
        use_stream: Whether to stream the response.
        
    Returns:
        Response text or a generator of response chunks.
    """
    logger.info("Starting legal analysis pipeline (history length: %d, streaming: %s)", len(conversation_history), use_stream)
    
    # Retrieve relevant legal context
    context_text, source_metadata = get_relevant_context(scenario)
    logger.info("Retrieved %d legal sources from knowledge base", len(source_metadata))
    
    # Build the analysis prompt with context
    if not conversation_history:
        # First message: use the structured analysis prompt
        enhanced_query = get_analysis_prompt(scenario, context_text)
        messages = [{"role": "user", "content": enhanced_query}]
    else:
        # Follow-up: include history and add context if relevant
        messages = []
        for msg in conversation_history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        
        user_message = scenario
        if context_text:
            user_message += f"\n\n[Additional Context: {context_text}]"
        messages.append({"role": "user", "content": user_message})
    
    system_prompt = get_system_prompt()
    logger.info("Dispatching prompt to Gemini model '%s'...", chatbot.model or "not set")
    
    if use_stream:
        return chatbot.chat_stream(messages, system_prompt)
    else:
        return chatbot.chat(messages, system_prompt)


def generate_conversation_title(first_message: str) -> str:
    """Generate a short title for a conversation."""
    return chatbot.generate_title(first_message)


def get_scenario_sources(query: str) -> list[dict]:
    """Get relevant legal source metadata for a query."""
    _, source_metadata = get_relevant_context(query)
    return source_metadata


def is_api_configured() -> bool:
    """Check if the Gemini API key is configured."""
    return chatbot.is_configured


def get_model_name() -> str:
    """Get the configured model name (or 'not set' if GEMINI_MODEL is missing)."""
    return chatbot.model if chatbot.is_model_configured else "not set"
