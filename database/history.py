"""NyayaAI Conversation history management."""
import sqlite3
from datetime import datetime
from typing import Optional
from database.db import get_connection


def create_conversation(title: str = "New Legal Analysis") -> int:
    """Create a new conversation and return its ID."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO conversations (title) VALUES (?)",
            (title,)
        )
        conn.commit()
        return cursor.lastrowid
    except sqlite3.Error as e:
        conn.rollback()
        raise RuntimeError(f"Failed to create conversation: {e}") from e
    finally:
        conn.close()


def save_message(conversation_id: int, role: str, content: str) -> int:
    """Save a message to a conversation. Returns the message ID."""
    if role not in ('user', 'assistant', 'system'):
        raise ValueError(f"Invalid role: {role}")
    if not content or not content.strip():
        raise ValueError("Message content cannot be empty")
    
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
            (conversation_id, role, content)
        )
        # Update conversation timestamp
        conn.execute(
            "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (conversation_id,)
        )
        conn.commit()
        return cursor.lastrowid
    except sqlite3.Error as e:
        conn.rollback()
        raise RuntimeError(f"Failed to save message: {e}") from e
    finally:
        conn.close()


def get_conversations() -> list[dict]:
    """Get all conversations ordered by most recent update."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, title, created_at, updated_at FROM conversations ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_messages(conversation_id: int) -> list[dict]:
    """Get all messages for a conversation in chronological order."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, conversation_id, role, content, created_at FROM messages WHERE conversation_id = ? ORDER BY created_at ASC, id ASC",
            (conversation_id,)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_conversation(conversation_id: int) -> Optional[dict]:
    """Get a single conversation by ID."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, title, created_at, updated_at FROM conversations WHERE id = ?",
            (conversation_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_conversation_title(conversation_id: int, title: str):
    """Update a conversation's title."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE conversations SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (title, conversation_id)
        )
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        raise RuntimeError(f"Failed to update title: {e}") from e
    finally:
        conn.close()


def delete_conversation(conversation_id: int):
    """Delete a conversation and all its messages (CASCADE)."""
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM conversations WHERE id = ?",
            (conversation_id,)
        )
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        raise RuntimeError(f"Failed to delete conversation: {e}") from e
    finally:
        conn.close()


def delete_last_message(conversation_id: int) -> bool:
    """Delete the most recent message in a conversation. Returns True if a message was deleted."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id FROM messages WHERE conversation_id = ? ORDER BY created_at DESC, id DESC LIMIT 1",
            (conversation_id,)
        ).fetchone()
        if row:
            conn.execute("DELETE FROM messages WHERE id = ?", (row["id"],))
            conn.commit()
            return True
        return False
    except sqlite3.Error as e:
        conn.rollback()
        raise RuntimeError(f"Failed to delete last message: {e}") from e
    finally:
        conn.close()


def get_message_count(conversation_id: int) -> int:
    """Get the number of messages in a conversation."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) as count FROM messages WHERE conversation_id = ?",
            (conversation_id,)
        ).fetchone()
        return row['count'] if row else 0
    finally:
        conn.close()
