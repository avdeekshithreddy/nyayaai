"""
NyayaAI Test Suite
Tests for deterministic utilities, database operations, and configuration.
Does NOT require paid API calls.
"""
import os
import sys
import sqlite3
import pytest
import tempfile
import json

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ============================================================
# Utility tests
# ============================================================
class TestHelpers:
    """Test utils/helpers.py functions."""

    def test_sanitize_input_strips_whitespace(self):
        from utils.helpers import sanitize_input

        assert sanitize_input("  hello   world  ") == "hello world"

    def test_sanitize_input_empty(self):
        from utils.helpers import sanitize_input

        assert sanitize_input("") == ""
        assert sanitize_input(None) == ""

    def test_truncate_text(self):
        from utils.helpers import truncate_text

        assert truncate_text("short", 100) == "short"
        assert len(truncate_text("a" * 200, 100)) <= 100
        assert truncate_text("a" * 200, 100).endswith("...")

    def test_truncate_text_empty(self):
        from utils.helpers import truncate_text

        assert truncate_text("", 50) == ""

    def test_validate_scenario_valid(self):
        from utils.helpers import validate_scenario

        valid, msg = validate_scenario("My landlord is refusing to return my deposit after vacating.")
        assert valid is True
        assert msg == ""

    def test_validate_scenario_too_short(self):
        from utils.helpers import validate_scenario

        valid, msg = validate_scenario("Hi")
        assert valid is False
        assert "more detail" in msg.lower() or "10 characters" in msg.lower()

    def test_validate_scenario_empty(self):
        from utils.helpers import validate_scenario

        valid, msg = validate_scenario("")
        assert valid is False

    def test_validate_scenario_too_long(self):
        from utils.helpers import validate_scenario

        valid, msg = validate_scenario("x" * 10001)
        assert valid is False
        assert "10,000" in msg

    def test_format_timestamp_invalid(self):
        from utils.helpers import format_timestamp

        result = format_timestamp("not-a-date")
        assert result == "not-a-date"

    def test_format_timestamp_empty(self):
        from utils.helpers import format_timestamp

        assert format_timestamp("") == ""

    def test_generate_report(self):
        from utils.helpers import generate_report

        messages = [
            {"role": "user", "content": "Test question"},
            {"role": "assistant", "content": "Test answer"},
        ]
        report = generate_report("Test Title", messages)
        assert "Test Title" in report
        assert "Test question" in report
        assert "Test answer" in report
        assert "Disclaimer" in report
        assert "NyayaAI" in report

    def test_generate_report_with_sources(self):
        from utils.helpers import generate_report

        messages = [{"role": "user", "content": "Q"}]
        sources = [{"title": "Indian Contract Act", "authority": "Ministry of Law", "url": "https://example.com"}]
        report = generate_report("T", messages, sources)
        assert "Indian Contract Act" in report
        assert "Ministry of Law" in report

    def test_extract_summary_from_messages(self):
        from utils.helpers import extract_summary_from_messages

        msgs = [{"role": "user", "content": "This is my legal problem about property dispute"}]
        summary = extract_summary_from_messages(msgs)
        assert "property" in summary.lower()

    def test_extract_summary_empty(self):
        from utils.helpers import extract_summary_from_messages

        assert "No conversation" in extract_summary_from_messages([])

    def test_count_sources_in_response(self):
        from utils.helpers import count_sources_in_response

        text = "Under Section 138 of the Negotiable Instruments Act, and Article 21 of the Constitution"
        count = count_sources_in_response(text)
        assert count >= 2


# ============================================================
# Database tests (using a temporary database)
# ============================================================
class TestDatabase:
    """Test database operations using a temporary database."""

    @pytest.fixture(autouse=True)
    def setup_temp_db(self, tmp_path, monkeypatch):
        """Create a temporary database for each test."""
        temp_db = str(tmp_path / "test_nyayaai.db")
        monkeypatch.setattr("database.db.DB_PATH", temp_db)

        # Re-initialize tables in the temp db
        from database.db import init_db
        init_db()

    def test_create_conversation(self):
        from database.history import create_conversation, get_conversation

        conv_id = create_conversation("Test Legal Query")
        assert conv_id is not None
        assert conv_id > 0

        conv = get_conversation(conv_id)
        assert conv is not None
        assert conv["title"] == "Test Legal Query"

    def test_create_conversation_default_title(self):
        from database.history import create_conversation, get_conversation

        conv_id = create_conversation()
        conv = get_conversation(conv_id)
        assert conv["title"] == "New Legal Analysis"

    def test_save_and_get_messages(self):
        from database.history import create_conversation, save_message, get_messages

        conv_id = create_conversation("Test")
        save_message(conv_id, "user", "What is Article 21?")
        save_message(conv_id, "assistant", "Article 21 guarantees Right to Life.")

        msgs = get_messages(conv_id)
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "What is Article 21?"
        assert msgs[1]["role"] == "assistant"

    def test_save_message_invalid_role(self):
        from database.history import create_conversation, save_message

        conv_id = create_conversation()
        with pytest.raises(ValueError, match="Invalid role"):
            save_message(conv_id, "invalid", "test")

    def test_save_message_empty_content(self):
        from database.history import create_conversation, save_message

        conv_id = create_conversation()
        with pytest.raises(ValueError, match="empty"):
            save_message(conv_id, "user", "")

    def test_get_conversations(self):
        from database.history import create_conversation, get_conversations

        create_conversation("First")
        create_conversation("Second")

        convs = get_conversations()
        assert len(convs) >= 2
        titles = [c["title"] for c in convs]
        assert "First" in titles
        assert "Second" in titles

    def test_update_conversation_title(self):
        from database.history import (
            create_conversation,
            update_conversation_title,
            get_conversation,
        )

        conv_id = create_conversation("Old Title")
        update_conversation_title(conv_id, "New Title")
        conv = get_conversation(conv_id)
        assert conv["title"] == "New Title"

    def test_delete_conversation(self):
        from database.history import (
            create_conversation,
            save_message,
            delete_conversation,
            get_conversation,
            get_messages,
        )

        conv_id = create_conversation("To Delete")
        save_message(conv_id, "user", "test message")
        delete_conversation(conv_id)

        assert get_conversation(conv_id) is None
        assert get_messages(conv_id) == []

    def test_get_message_count(self):
        from database.history import create_conversation, save_message, get_message_count

        conv_id = create_conversation()
        assert get_message_count(conv_id) == 0

        save_message(conv_id, "user", "Hello")
        save_message(conv_id, "assistant", "Hi")
        assert get_message_count(conv_id) == 2

    def test_get_nonexistent_conversation(self):
        from database.history import get_conversation

        assert get_conversation(99999) is None

    def test_messages_ordered_chronologically(self):
        from database.history import create_conversation, save_message, get_messages

        conv_id = create_conversation()
        save_message(conv_id, "user", "First")
        save_message(conv_id, "assistant", "Second")
        save_message(conv_id, "user", "Third")

        msgs = get_messages(conv_id)
        contents = [m["content"] for m in msgs]
        assert contents == ["First", "Second", "Third"]


# ============================================================
# Legal source retrieval tests
# ============================================================
class TestRetrieval:
    """Test legal source retrieval."""

    def test_load_legal_sources(self):
        from backend.retrieval import load_legal_sources

        sources = load_legal_sources()
        assert len(sources) > 0

    def test_search_sources_finds_relevant(self):
        from backend.retrieval import search_sources

        results = search_sources("consumer complaint refund")
        assert len(results) > 0
        titles = [s.title for s in results]
        assert any("consumer" in t.lower() for t in titles)

    def test_search_sources_criminal(self):
        from backend.retrieval import search_sources

        results = search_sources("criminal offense theft punishment")
        assert len(results) > 0
        titles = [s.title for s in results]
        assert any("nyaya" in t.lower() or "penal" in t.lower() for t in titles)

    def test_search_sources_empty_query(self):
        from backend.retrieval import search_sources

        results = search_sources("")
        # Even with empty query, short terms are filtered so no crash
        assert isinstance(results, list)

    def test_get_relevant_context(self):
        from backend.retrieval import get_relevant_context

        context, metadata = get_relevant_context("property dispute land transfer")
        assert isinstance(context, str)
        assert isinstance(metadata, list)

    def test_get_all_sources_metadata(self):
        from backend.retrieval import get_all_sources_metadata

        sources = get_all_sources_metadata()
        assert len(sources) > 0
        assert "title" in sources[0]
        assert "category" in sources[0]

    def test_legal_source_to_dict(self):
        from backend.retrieval import LegalSource

        data = {
            "title": "Test Act",
            "category": "Test",
            "description": "A test",
            "authority": "Test Auth",
            "url": "https://example.com",
            "keywords": ["test"],
            "year": "2024",
            "status": "active",
        }
        source = LegalSource(data)
        d = source.to_dict()
        assert d["title"] == "Test Act"
        assert d["status"] == "active"


# ============================================================
# API configuration tests (no paid calls)
# ============================================================
class TestAPIConfiguration:
    """Test API configuration handling."""

    def test_chatbot_import(self):
        from backend.chatbot import NyayaChatbot

        bot = NyayaChatbot()
        assert hasattr(bot, "chat")
        assert hasattr(bot, "chat_stream")
        assert hasattr(bot, "is_configured")

    def test_chatbot_masked_key_unconfigured(self):
        from backend.chatbot import NyayaChatbot

        bot = NyayaChatbot()
        bot.api_key = ""
        assert "Not configured" in bot.get_masked_key()

    def test_chatbot_masked_key_configured(self):
        from backend.chatbot import NyayaChatbot

        bot = NyayaChatbot()
        bot.api_key = "sk-test1234567890abcdef"
        masked = bot.get_masked_key()
        assert "sk-t" in masked
        assert "cdef" in masked
        assert "1234567890" not in masked

    def test_chatbot_not_configured_placeholder(self):
        from backend.chatbot import NyayaChatbot

        bot = NyayaChatbot()
        bot.api_key = "your_openai_api_key_here"
        assert bot.is_configured is False

    def test_chatbot_error_without_key(self):
        from backend.chatbot import NyayaChatbot, ChatbotError

        bot = NyayaChatbot()
        bot.api_key = ""
        with pytest.raises(ChatbotError, match="not configured"):
            _ = bot.client

    def test_model_name(self):
        from backend.legal_analyzer import get_model_name

        model = get_model_name()
        assert isinstance(model, str)
        assert len(model) > 0


# ============================================================
# Prompts tests
# ============================================================
class TestPrompts:
    """Test prompt generation."""

    def test_system_prompt_exists(self):
        from backend.prompts import get_system_prompt

        prompt = get_system_prompt()
        assert "NyayaAI" in prompt
        assert "Indian" in prompt
        assert "fabricat" in prompt.lower()

    def test_analysis_prompt(self):
        from backend.prompts import get_analysis_prompt

        prompt = get_analysis_prompt("My landlord won't return deposit")
        assert "landlord" in prompt
        assert "Scenario Summary" in prompt

    def test_analysis_prompt_with_context(self):
        from backend.prompts import get_analysis_prompt

        prompt = get_analysis_prompt("test", "Some legal context here")
        assert "Knowledge Base" in prompt
        assert "Some legal context here" in prompt

    def test_title_prompt(self):
        from backend.prompts import get_title_prompt

        prompt = get_title_prompt("What are my rights if my employer fires me?")
        assert "employer" in prompt or "fires" in prompt


# ============================================================
# Error Classification and Safety Tests
# ============================================================
class TestErrorHandlingAndSafety:
    """Test safe error classification, scrubbing, and message deletion."""

    def test_delete_last_message(self, tmp_path, monkeypatch):
        temp_db = str(tmp_path / "test_delete_last.db")
        monkeypatch.setattr("database.db.DB_PATH", temp_db)
        from database.db import init_db
        from database.history import create_conversation, save_message, get_messages, delete_last_message

        init_db()
        conv_id = create_conversation("Test Delete Last")
        save_message(conv_id, "user", "Message 1")
        save_message(conv_id, "assistant", "Message 2")
        save_message(conv_id, "user", "Message 3 (Failed)")

        assert len(get_messages(conv_id)) == 3
        deleted = delete_last_message(conv_id)
        assert deleted is True

        msgs = get_messages(conv_id)
        assert len(msgs) == 2
        assert msgs[-1]["content"] == "Message 2"

    def test_scrub_secrets_redacts_api_key(self):
        from backend.chatbot import scrub_secrets

        sample = "Error with key sk-proj-1234567890abcdefABCDEF123456 in header Bearer sk-secret"
        cleaned = scrub_secrets(sample)
        assert "sk-proj-1234567890abcdefABCDEF123456" not in cleaned
        assert "[REDACTED_API_KEY]" in cleaned

    def test_classify_quota_exceeded_error(self):
        from backend.chatbot import NyayaChatbot, ChatbotError

        bot = NyayaChatbot()
        raw_error = Exception("Error code: 429 - You have no credits remaining. Add credits to continue.")
        classified = bot._classify_error(raw_error, stage="test")
        assert isinstance(classified, ChatbotError)
        assert "quota" in str(classified).lower() or "credits" in str(classified).lower()

    def test_test_connection_unconfigured(self):
        from backend.chatbot import NyayaChatbot

        bot = NyayaChatbot()
        bot.api_key = ""
        result = bot.test_connection()
        assert result["ok"] is False
        assert result["status"] == "unconfigured"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

