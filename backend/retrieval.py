"""NyayaAI Legal knowledge base retrieval system."""
import json
import os
from typing import Optional

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
SOURCES_FILE = os.path.join(DATA_DIR, "legal_sources.json")
DOCUMENTS_DIR = os.path.join(DATA_DIR, "legal_documents")


class LegalSource:
    """Represents a legal source with metadata."""

    def __init__(self, data: dict):
        self.title = data.get("title", "")
        self.category = data.get("category", "")
        self.description = data.get("description", "")
        self.authority = data.get("authority", "")
        self.url = data.get("url", "")
        self.keywords = data.get("keywords", [])
        self.year = data.get("year", "")
        self.status = data.get("status", "active")
        self.replaced_by = data.get("replaced_by", "")
        self.local_file = data.get("local_file", "")

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "category": self.category,
            "description": self.description,
            "authority": self.authority,
            "url": self.url,
            "keywords": self.keywords,
            "year": self.year,
            "status": self.status,
            "replaced_by": self.replaced_by,
        }

    def __repr__(self):
        return f"LegalSource(title='{self.title}')"


def load_legal_sources() -> list[LegalSource]:
    """Load legal source metadata from JSON file."""
    if not os.path.exists(SOURCES_FILE):
        return []
    try:
        with open(SOURCES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        sources = data.get("sources", []) if isinstance(data, dict) else data
        return [LegalSource(s) for s in sources]
    except (json.JSONDecodeError, IOError):
        return []


def search_sources(query: str, top_k: int = 5) -> list[LegalSource]:
    """Search legal sources by keyword matching.
    
    Simple keyword-based search suitable for the initial version.
    Can be upgraded to vector search / RAG later.
    """
    sources = load_legal_sources()
    if not sources:
        return []

    query_lower = query.lower()
    query_terms = set(query_lower.split())

    scored = []
    for source in sources:
        score = 0
        searchable = f"{source.title} {source.description} {source.category} {' '.join(source.keywords)}".lower()
        
        # Exact phrase match in title gets highest score
        if query_lower in source.title.lower():
            score += 10
        
        # Keyword matches
        for term in query_terms:
            if len(term) < 3:
                continue
            if term in searchable:
                score += 2
            # Keyword list match bonus
            for kw in source.keywords:
                if term in kw.lower():
                    score += 3

        if score > 0:
            scored.append((score, source))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [s for _, s in scored[:top_k]]


def load_local_document(filename: str) -> Optional[str]:
    """Load content from a local legal document file."""
    if not filename:
        return None
    filepath = os.path.join(DOCUMENTS_DIR, filename)
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except IOError:
        return None


def get_relevant_context(query: str) -> tuple[str, list[dict]]:
    """Get relevant legal context for a query.
    
    Returns:
        Tuple of (context_text, source_metadata_list)
    """
    sources = search_sources(query)
    if not sources:
        return "", []

    context_parts = []
    source_metadata = []

    for source in sources:
        info = f"- {source.title}"
        if source.year:
            info += f" ({source.year})"
        if source.description:
            info += f": {source.description}"
        if source.status == "replaced":
            info += f" [Note: Replaced by {source.replaced_by}]"
        
        # Try loading local document content
        local_content = load_local_document(source.local_file)
        if local_content:
            info += f"\n  Content excerpt: {local_content[:500]}"
        
        context_parts.append(info)
        source_metadata.append(source.to_dict())

    context_text = "Relevant Legal Sources:\n" + "\n".join(context_parts)
    return context_text, source_metadata


def get_all_sources_metadata() -> list[dict]:
    """Get metadata for all available legal sources."""
    sources = load_legal_sources()
    return [s.to_dict() for s in sources]
