<<<<<<< HEAD
# NyayaAI — Indian Legal Scenario Analyzer

An AI-powered application that helps users understand Indian legal situations by describing their problems in natural language. Built with Streamlit, OpenAI, and SQLite.

> ⚠️ **Disclaimer:** NyayaAI provides general legal information for educational purposes. It is not a substitute for advice from a qualified Indian lawyer. Laws and outcomes depend on the facts and applicable law.

---

## Features

- 🤖 **AI Legal Chatbot** — Describe your legal situation in natural language and receive structured analysis
- ⚖️ **Indian Law Focus** — Covers BNS, BNSS, BSA, Constitution, Consumer Protection, IT Act, Family Law, Property Law, and more
- 💬 **Conversation Context** — Follow-up questions retain conversation history
- 💾 **Persistent History** — Conversations are saved locally in SQLite
- 📚 **Legal Knowledge Base** — Retrieval-augmented responses with 22+ Indian legal sources
- 📥 **Export Reports** — Download analysis as Markdown reports
- 🌐 **Multi-language Support** — Responses in English, Hindi, Tamil, Telugu, and more
- 🎨 **Futuristic UI** — Dark workspace theme with connected-card design

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Frontend | Streamlit |
| Backend | Python |
| Database | SQLite |
| AI Provider | OpenAI API |
| SDK | Official OpenAI Python SDK |
| Environment | python-dotenv |
| Styling | Custom CSS |
| Testing | pytest |

---

## Project Structure

```
NyayaAI/
├── app.py                      # Main Streamlit application
├── requirements.txt            # Python dependencies
├── .env                        # Environment variables (not in git)
├── .env.example                # Example environment config
├── .gitignore                  # Git ignore rules
├── README.md                   # This file
├── backend/
│   ├── __init__.py             # Backend package
│   ├── chatbot.py              # OpenAI API client
│   ├── legal_analyzer.py       # Legal analysis engine
│   ├── prompts.py              # System prompts and templates
│   └── retrieval.py            # Legal knowledge retrieval
├── database/
│   ├── __init__.py             # Database package
│   ├── db.py                   # SQLite initialization
│   └── history.py              # Conversation CRUD operations
├── data/
│   ├── legal_documents/        # Local legal documents (optional)
│   └── legal_sources.json      # Legal source metadata
├── utils/
│   ├── __init__.py             # Utilities package
│   └── helpers.py              # Validation, formatting, export
├── assets/
│   └── style.css               # Futuristic dark theme CSS
└── tests/
    └── test_analyzer.py        # Automated test suite
```

---

## Setup & Installation

### Prerequisites

- Python 3.10+
- An OpenAI API key ([Get one here](https://platform.openai.com/api-keys))

### 1. Create Virtual Environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 2. Install Dependencies

```powershell
pip install -r requirements.txt
```

### 3. Configure API Key

Edit the `.env` file in the project root:

```
OPENAI_API_KEY=sk-your-actual-api-key-here
OPENAI_MODEL=gpt-4.1-mini
```

**Security Notes:**
- Never commit `.env` to version control
- Never share your API key
- The `.gitignore` already excludes `.env`

### 4. Run the Application

```powershell
streamlit run app.py
```

The application will open in your browser at `http://localhost:8501`.

---

## Running Tests

```powershell
.venv\Scripts\python.exe -m pytest tests/ -v
```

Tests cover:
- Input validation and sanitization
- Database CRUD operations
- Legal source retrieval
- API configuration handling
- Prompt generation
- Report generation

No paid API calls are required for automated tests.

---

## Usage Guide

1. **Start a New Analysis** — Click "New Legal Analysis" in the sidebar or type in the chat input
2. **Describe Your Situation** — Write your legal problem in natural language
3. **Review the Analysis** — The AI provides structured analysis with relevant Indian laws
4. **Ask Follow-ups** — Continue the conversation with additional questions
5. **Export Reports** — Download the analysis as a Markdown report
6. **View History** — Access and continue previous conversations

### Example Questions

- "My landlord is refusing to return my security deposit. What are my legal options?"
- "My employer hasn't paid my salary for 3 months. What legal steps can I take?"
- "Someone is posting defamatory content about me on social media. What remedies are available?"

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | Your OpenAI API key | *(required)* |
| `OPENAI_MODEL` | OpenAI model to use | `gpt-4.1-mini` |

### Supported Models

- `gpt-4.1-mini` (recommended — fast, affordable)
- `gpt-4o-mini`
- `gpt-4o`
- `gpt-4.1`

---

## Legal Sources

The knowledge base includes metadata for 22+ Indian legal sources:

- Constitution of India
- Bharatiya Nyaya Sanhita (BNS) — replaced IPC
- Bharatiya Nagarik Suraksha Sanhita (BNSS) — replaced CrPC
- Bharatiya Sakshya Adhiniyam (BSA) — replaced Indian Evidence Act
- Indian Contract Act, 1872
- Consumer Protection Act, 2019
- Information Technology Act, 2000
- Hindu Marriage Act, 1955
- Transfer of Property Act, 1882
- And more...

Sources reference official URLs from `indiacode.nic.in` and `legislative.gov.in`.

---

## Limitations

- Provides **educational information only**, not legal advice
- Cannot guarantee accuracy of all legal citations
- Does not replace a qualified Indian lawyer
- Requires internet access for AI responses
- API usage incurs OpenAI charges
- No live verification of legal sources

---

## License

This project is a college mini-project for educational purposes.
=======
# nyayaai
>>>>>>> aaca1078ae8c6befa78f8cccae65b2ee2a7b47bf
