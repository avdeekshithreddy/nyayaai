"""NyayaAI Backend package."""
from backend.chatbot import chatbot, ChatbotError, NyayaChatbot
from backend.legal_analyzer import (
    analyze_scenario,
    generate_conversation_title,
    get_scenario_sources,
    is_api_configured,
    get_model_name,
)
