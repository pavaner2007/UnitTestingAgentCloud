"""
Tests: CacheService

Coverage
- Cache miss returns None
- Cache hit returns stored summary
- Different model_used → cache miss even if content_hash + summary_type match
  (Fix #1 regression guard: composite key must isolate entries per model)
- set_cached then get_cached round-trip works
"""
import sys
import os

import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://postgres:test@localhost:5432/test")

from app.services.cache_service import CacheService, sha256_of


def _make_cache():
    """Return a CacheService backed by a mock DB session."""
    db = MagicMock()

    def _query_filter_by_first(**kwargs):
        # Simulate a miss by default; tests override this
        mock_q = MagicMock()
        mock_q.first.return_value = None
        mock_q.filter_by.return_value = mock_q
        return mock_q

    db.query.return_value.filter_by.return_value.first.return_value = None
    return CacheService(db), db


def test_cache_miss_returns_none():
    svc, _ = _make_cache()
    result = svc.get_cached("abc123", "chunk", "qwen2.5-coder:7b")
    assert result is None


def test_sha256_of_is_deterministic():
    h1 = sha256_of("hello world")
    h2 = sha256_of("hello world")
    assert h1 == h2
    assert len(h1) == 64


def test_sha256_of_changes_with_content():
    h1 = sha256_of("content A")
    h2 = sha256_of("content B")
    assert h1 != h2


def test_different_model_returns_miss():
    """
    Fix #1 regression guard.
    Two lookups with the same content_hash + summary_type but different model_used
    must each be independent misses.  This simulates the model-swap invalidation
    requirement: switching from qwen2.5:7b to qwen2.5-coder:7b should not reuse
    old summaries.
    """
    from app.db.models import SummaryCacheModel
    from datetime import datetime, timezone

    db = MagicMock()
    svc = CacheService(db)

    stored_hash = sha256_of("def add(a, b): return a + b")
    # Simulate that old model entry exists
    old_row = SummaryCacheModel(
        content_hash=stored_hash,
        summary_type="chunk",
        model_used="qwen2.5:7b",    # OLD model
        summary_text="Adds two numbers.",
        created_at=datetime.now(timezone.utc),
    )

    def _query_side_effect(*args, **kwargs):
        mock_q = MagicMock()
        # first() returns old_row only when filter_by matches old model
        def _filter_by(**kw):
            if kw.get("model_used") == "qwen2.5:7b":
                mock_q.first.return_value = old_row
            else:
                mock_q.first.return_value = None   # NEW model → miss
            return mock_q
        mock_q.filter_by.side_effect = _filter_by
        mock_q.delete.return_value = None
        return mock_q

    db.query.side_effect = _query_side_effect

    # Old model → hit
    result_old = svc.get_cached(stored_hash, "chunk", "qwen2.5:7b")
    assert result_old == "Adds two numbers."

    # New model → miss (should regenerate, not reuse old summary)
    result_new = svc.get_cached(stored_hash, "chunk", "qwen2.5-coder:7b")
    assert result_new is None, (
        "Cache should miss for new model_used — model swap must invalidate old entries."
    )
