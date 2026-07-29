"""
Tests for QAChatAgent, EmbeddingService, and VectorSearchService.

Covers:
- Cosine similarity utility
- Vector store + retrieve round-trip
- Basic Q&A answer flow (semantic only)
- PINNED retrieval when a file:line reference is present in the question
- TARGETED follow-up retrieval when a symbol is missing from initial context
- _parse_file_line_refs helper
- _parse_symbol_refs helper
"""
from unittest.mock import MagicMock, patch
import pytest

from app.db.models import ChunkEmbeddingModel
from app.services.embedding_service import EmbeddingService
from app.services.vector_search_service import VectorSearchService, ChunkResult, _cosine_similarity
from app.agents.qa_chat_agent import (
    QAChatAgent,
    _parse_file_line_refs,
    _parse_symbol_refs,
    _dedupe_chunks,
)


# ── Utility: build a mock ChunkEmbeddingModel row ────────────────────────────

def _make_row(file_path, content, start_line, end_line, repo_id="repo1"):
    return ChunkEmbeddingModel(
        repo_analysis_id=repo_id,
        file_path=file_path,
        chunk_content=content,
        embedding_json="[1.0, 0.0, 0.0]",
        start_line=start_line,
        end_line=end_line,
    )


# ── Cosine similarity ─────────────────────────────────────────────────────────

def test_cosine_similarity():
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    v3 = [0.0, 1.0, 0.0]
    assert pytest.approx(_cosine_similarity(v1, v2), 0.001) == 1.0
    assert pytest.approx(_cosine_similarity(v1, v3), 0.001) == 0.0


# ── VectorSearchService ───────────────────────────────────────────────────────

def test_vector_search_store_and_retrieve():
    db = MagicMock()
    mock_query = db.query.return_value
    mock_filter = mock_query.filter.return_value

    m1 = _make_row("app/main.py", "def main(): pass", 1, 5)
    mock_filter.all.return_value = [m1]

    svc = VectorSearchService(db)
    results = svc.similarity_search("test_id", [1.0, 0.0, 0.0], top_k=1)

    assert len(results) == 1
    assert results[0].file_path == "app/main.py"
    assert results[0].score > 0.99


# ── _parse_file_line_refs ─────────────────────────────────────────────────────

def test_parse_file_line_refs_with_line():
    refs = _parse_file_line_refs("Look at app/main.py:321 — what's wrong?")
    assert len(refs) == 1
    assert refs[0]["file"] == "app/main.py"
    assert refs[0]["line"] == 321


def test_parse_file_line_refs_bare_filename():
    refs = _parse_file_line_refs("Can you explain the error in auth_service.py?")
    files = [r["file"] for r in refs]
    assert "auth_service.py" in files


def test_parse_file_line_refs_no_match():
    refs = _parse_file_line_refs("What is authentication?")
    assert refs == []


def test_parse_file_line_refs_with_range():
    refs = _parse_file_line_refs("AGENT/main.py:10-40 explain this")
    assert refs[0]["file"] == "AGENT/main.py"
    assert refs[0]["line"] == 10


# ── _parse_symbol_refs ────────────────────────────────────────────────────────

def test_parse_symbol_refs_finds_snake_case():
    syms = _parse_symbol_refs("What does call_llm_json do?")
    assert "call_llm_json" in syms


def test_parse_symbol_refs_ignores_stopwords():
    syms = _parse_symbol_refs("explain the error in this file")
    # None of the tokens should be plain English stop-words
    assert "the_error" not in syms
    assert "this_file" not in syms


def test_parse_symbol_refs_empty_question():
    assert _parse_symbol_refs("what is this?") == []


# ── _dedupe_chunks ────────────────────────────────────────────────────────────

def test_dedupe_chunks_removes_duplicates():
    c1 = ChunkResult("a.py", "x", 1, 10, 0.9)
    c2 = ChunkResult("a.py", "x", 1, 10, 0.7)   # duplicate
    c3 = ChunkResult("b.py", "y", 5, 20, 0.6)
    result = _dedupe_chunks([c1, c2, c3])
    assert len(result) == 2
    assert result[0].file_path == "a.py"
    assert result[1].file_path == "b.py"


# ── QAChatAgent — basic semantic answer ──────────────────────────────────────

def test_qa_chat_agent_answer_question():
    db = MagicMock()
    agent = QAChatAgent(db)

    agent.embed_service.embed_text = MagicMock(return_value=[1.0, 0.0, 0.0])
    agent.vector_service.similarity_search = MagicMock(return_value=[
        ChunkResult("app/auth.py", "def login(): pass", 10, 20, 0.95)
    ])
    agent.groq_service.ask_question_with_context = MagicMock(
        return_value="Authentication is handled in `app/auth.py:10-20` via the `login` function."
    )
    # No DB rows needed for pinned (no file:line in question)
    db.query.return_value.filter.return_value.all.return_value = []

    res = agent.answer_question("analysis_123", "Where is auth handled?")

    assert "Authentication is handled" in res["answer"]
    assert len(res["citations"]) >= 1
    assert res["citations"][0]["file"] == "app/auth.py"
    assert res["citations"][0]["start_line"] == 10


# ── QAChatAgent — PINNED retrieval (file:line in question) ───────────────────

def test_qa_chat_agent_pinned_retrieval():
    """When the question contains a file:line ref, that file's chunk must appear first."""
    db = MagicMock()
    agent = QAChatAgent(db)

    # Row that matches the referenced file
    pinned_row = _make_row("app/agents/qa_chat_agent.py", "def answer_question(): ...", 310, 340)

    agent.embed_service.embed_text = MagicMock(return_value=[1.0, 0.0, 0.0])
    agent.vector_service.similarity_search = MagicMock(return_value=[
        ChunkResult("app/utils.py", "def helper(): pass", 1, 10, 0.72)
    ])
    agent.groq_service.ask_question_with_context = MagicMock(
        return_value="The error at line 321 is a KeyError because..."
    )
    db.query.return_value.filter.return_value.all.return_value = [pinned_row]

    res = agent.answer_question(
        "analysis_123",
        "qa_chat_agent.py:321 explain this error",
    )

    assert "error" in res["answer"].lower()
    # Pinned file must appear in citations
    cited_files = [c["file"] for c in res["citations"]]
    assert any("qa_chat_agent" in f for f in cited_files), (
        f"Expected qa_chat_agent.py in citations, got: {cited_files}"
    )


# ── QAChatAgent — TARGETED follow-up (missing symbol) ────────────────────────

def test_qa_chat_agent_targeted_lookup_for_missing_symbol():
    """When a symbol from the question isn't in initial context, targeted lookup fires."""
    db = MagicMock()
    agent = QAChatAgent(db)

    target_row = _make_row(
        "app/services/llm_service.py",
        "def call_llm_json(prompt, schema): return groq.complete(prompt)",
        50, 70,
    )

    agent.embed_service.embed_text = MagicMock(return_value=[1.0, 0.0, 0.0])
    # Semantic search returns unrelated chunks (no call_llm_json)
    agent.vector_service.similarity_search = MagicMock(return_value=[
        ChunkResult("app/main.py", "def main(): pass", 1, 10, 0.6)
    ])
    agent.groq_service.ask_question_with_context = MagicMock(
        return_value="call_llm_json is defined in llm_service.py and calls groq.complete."
    )
    # DB rows include the target row for targeted lookup
    db.query.return_value.filter.return_value.all.return_value = [
        _make_row("app/main.py", "def main(): pass", 1, 10),
        target_row,
    ]

    res = agent.answer_question(
        "analysis_123",
        "What does call_llm_json do and where is it defined?",
    )

    assert res["answer"]
    # The targeted chunk for call_llm_json should appear in citations
    cited_files = [c["file"] for c in res["citations"]]
    assert any("llm_service" in f for f in cited_files), (
        f"Expected llm_service.py in citations via targeted lookup, got: {cited_files}"
    )
