"""
CacheService — content-addressed summary cache backed by PostgreSQL.

Cache key: (content_hash, summary_type, model_used)
- content_hash  : SHA-256 of the raw file/chunk content
- summary_type  : 'chunk' | 'file' | 'module'
- model_used    : exact Ollama model name (e.g. 'qwen2.5-coder:7b')

Keying on model_used ensures that swapping or upgrading a model naturally
invalidates old entries — a lookup for the new model name simply misses
and regenerates, instead of silently returning a stale summary.
"""
from __future__ import annotations

import hashlib
import logging

from sqlalchemy.orm import Session

from app.db.models import SummaryCacheModel

logger = logging.getLogger(__name__)


def sha256_of(content: str) -> str:
    """Return the SHA-256 hex digest of a UTF-8 encoded string."""
    return hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()


class CacheService:
    def __init__(self, db: Session) -> None:
        self._db = db

    # ── Public API ────────────────────────────────────────────────────────────

    def get_cached(
        self,
        content_hash: str,
        summary_type: str,
        model_used: str,
    ) -> str | None:
        """Return a cached summary string or None on cache miss.

        All three key components must match — different model_used → cache miss.
        """
        row = (
            self._db.query(SummaryCacheModel)
            .filter_by(
                content_hash=content_hash,
                summary_type=summary_type,
                model_used=model_used,
            )
            .first()
        )
        if row:
            logger.debug(
                "Cache HIT  type=%s model=%s hash=%s…",
                summary_type, model_used, content_hash[:8],
            )
            return row.summary_text
        logger.debug(
            "Cache MISS type=%s model=%s hash=%s…",
            summary_type, model_used, content_hash[:8],
        )
        return None

    def set_cached(
        self,
        content_hash: str,
        summary_type: str,
        summary_text: str,
        model_used: str,
    ) -> None:
        """Persist a summary to the cache (upsert via delete+insert for simplicity)."""
        try:
            # Delete any existing entry with this composite key, then insert fresh.
            self._db.query(SummaryCacheModel).filter_by(
                content_hash=content_hash,
                summary_type=summary_type,
                model_used=model_used,
            ).delete()
            row = SummaryCacheModel(
                content_hash=content_hash,
                summary_type=summary_type,
                model_used=model_used,
                summary_text=summary_text,
            )
            self._db.add(row)
            self._db.commit()
        except Exception as exc:
            self._db.rollback()
            logger.warning("Failed to write cache entry: %s", exc)
