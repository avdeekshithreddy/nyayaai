"""NyayaAI Database package."""
from database.db import init_db, get_connection
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
