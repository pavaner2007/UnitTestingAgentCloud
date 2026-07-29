"""
VectorSearchService — stores chunk vector embeddings and performs cosine similarity search.

Provides:
- store_chunk_embeddings(db, repo_id, chunks_with_vecs)
- similarity_search(db, repo_id, query_vec, top_k=5) -> list[ChunkResult]
"""
from __future__ import annotations

import json
import math
import logging
from dataclasses import dataclass
from typing import Any
from sqlalchemy.orm import Session

from app.db.models import ChunkEmbeddingModel

logger = logging.getLogger(__name__)


@dataclass
class ChunkResult:
    file_path: str
    chunk_content: str
    start_line: int
    end_line: int
    score: float


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class VectorSearchService:
    """Store chunk embeddings and run similarity search for Q&A retrieval."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def store_chunk_embeddings(
        self,
        repo_analysis_id: str,
        chunks_with_embeddings: list[dict[str, Any]],
    ) -> int:
        """
        Store a batch of chunk embedding records in the database.
        Each dict in chunks_with_embeddings:
          {"file_path": str, "content": str, "start_line": int, "end_line": int, "embedding": list[float]}
        """
        if not chunks_with_embeddings:
            return 0

        # Delete old embeddings for this repo run if re-analyzed
        try:
            self.db.query(ChunkEmbeddingModel).filter(
                ChunkEmbeddingModel.repo_analysis_id == repo_analysis_id
            ).delete()
        except Exception:
            pass

        count = 0
        for item in chunks_with_embeddings:
            vec = item.get("embedding")
            if not vec:
                continue
            model = ChunkEmbeddingModel(
                repo_analysis_id=repo_analysis_id,
                file_path=item.get("file_path", ""),
                chunk_content=item.get("content", ""),
                embedding_json=json.dumps(vec),
                start_line=item.get("start_line", 1),
                end_line=item.get("end_line", 1),
            )
            self.db.add(model)
            count += 1

        try:
            self.db.commit()
            logger.info("VectorSearchService: stored %d chunk embeddings for analysis %s", count, repo_analysis_id)
        except Exception as exc:
            self.db.rollback()
            logger.error("Failed to store chunk embeddings — %s", exc)

        return count

    def similarity_search(
        self,
        repo_analysis_id: str,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[ChunkResult]:
        """
        Retrieve top_k code chunks matching the query embedding by cosine similarity.
        """
        if not query_embedding:
            return []

        rows = (
            self.db.query(ChunkEmbeddingModel)
            .filter(ChunkEmbeddingModel.repo_analysis_id == repo_analysis_id)
            .all()
        )

        if not rows:
            logger.warning("No embeddings found in DB for repo_analysis_id=%s", repo_analysis_id)
            return []

        scored: list[ChunkResult] = []
        for r in rows:
            try:
                vec = json.loads(r.embedding_json)
                score = _cosine_similarity(query_embedding, vec)
                scored.append(ChunkResult(
                    file_path=r.file_path,
                    chunk_content=r.chunk_content,
                    start_line=r.start_line,
                    end_line=r.end_line,
                    score=score,
                ))
            except Exception:
                continue

        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[:top_k]
