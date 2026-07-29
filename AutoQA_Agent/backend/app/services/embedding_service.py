"""
EmbeddingService — Cloud vector embeddings service with pure Python local fallback.

Supports generating vector embeddings via:
  - Pure Python local feature vectorizer (384-dim, 0 dependencies, 0 external APIs required)
  - OpenAI Embeddings API (`text-embedding-3-small` if `OPENAI_API_KEY` provided)
  - Google Gemini Embeddings API (`text-embedding-004` if `GEMINI_API_KEY` provided)

Caches vector embeddings using `CacheService` keyed by `(content_hash, "embedding", model_name)`.
"""
from __future__ import annotations

import json
import math
import logging
import zlib
import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.cache_service import CacheService, sha256_of

logger = logging.getLogger(__name__)

_SUMMARY_TYPE = "embedding"
_LOCAL_EMBED_DIM = 384


class EmbeddingService:
    """Generates vector embeddings for code chunks and search queries."""

    def __init__(self, db: Session | None = None) -> None:
        self._cache = CacheService(db) if db else None
        self.provider = (settings.cloud_embed_provider or "local").lower().strip()
        self.model = settings.cloud_embed_model or "local-feature-384"

        self._openai_client = None
        if settings.openai_api_key:
            try:
                from openai import OpenAI
                self._openai_client = OpenAI(api_key=settings.openai_api_key)
            except Exception as exc:
                logger.warning("OpenAI SDK init failed in EmbeddingService: %s", exc)

    def embed_text(self, text: str) -> list[float] | None:
        """
        Generate float embedding vector for input text.
        Checks cache first, then executes vector generation.
        """
        if not text or not text.strip():
            return None

        # 1. Check cache
        if self._cache:
            h = sha256_of(text)
            cached_raw = self._cache.get_cached(h, _SUMMARY_TYPE, self.model)
            if cached_raw:
                try:
                    return json.loads(cached_raw)
                except Exception:
                    pass

        # 2. Generate vector
        vec = None
        if settings.openai_api_key and self.provider == "openai":
            vec = self._embed_openai(text)
        elif settings.gemini_api_key and self.provider == "gemini":
            vec = self._embed_gemini(text)
        else:
            vec = self._embed_local_features(text)

        # 3. Cache and return vector
        if vec and isinstance(vec, list) and len(vec) > 0:
            if self._cache:
                h = sha256_of(text)
                self._cache.set_cached(h, _SUMMARY_TYPE, json.dumps(vec), self.model)
            return vec

        return None

    def _embed_local_features(self, text: str) -> list[float]:
        """
        Pure Python subword & token feature vectorizer (384-dim).
        Requires zero external APIs, zero servers, and zero extra pip libraries.
        Produces normalized float vector for cosine similarity retrieval.
        """
        dim = _LOCAL_EMBED_DIM
        vec = [0.0] * dim
        tokens = [t.lower() for t in text.split() if t.strip()]

        for token in tokens:
            # 1. Full word hash
            w_idx = zlib.crc32(token.encode("utf-8")) % dim
            vec[w_idx] += 1.0

            # 2. Subword 3-gram hashes
            if len(token) >= 3:
                for i in range(len(token) - 2):
                    sub = token[i:i+3]
                    sub_idx = zlib.crc32(sub.encode("utf-8")) % dim
                    vec[sub_idx] += 0.5

        # L2 Normalization
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]

        return vec

    def _embed_openai(self, text: str) -> list[float] | None:
        key = settings.openai_api_key
        if not key:
            return self._embed_local_features(text)

        try:
            if self._openai_client:
                res = self._openai_client.embeddings.create(
                    input=[text],
                    model=self.model or "text-embedding-3-small"
                )
                return res.data[0].embedding

            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            payload = {"input": text, "model": self.model or "text-embedding-3-small"}
            resp = httpx.post("https://api.openai.com/v1/embeddings", json=payload, headers=headers, timeout=20.0)
            if resp.status_code == 200:
                data = resp.json()
                return data["data"][0]["embedding"]
        except Exception as exc:
            logger.error("OpenAI embedding failed: %s", exc)

        return self._embed_local_features(text)

    def _embed_gemini(self, text: str) -> list[float] | None:
        key = settings.gemini_api_key
        if not key:
            return self._embed_local_features(text)

        try:
            target_model = self.model if "embedding" in self.model else "text-embedding-004"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:embedContent?key={key}"
            payload = {"content": {"parts": [{"text": text}]}}
            resp = httpx.post(url, json=payload, timeout=20.0)
            if resp.status_code == 200:
                data = resp.json()
                return data["embedding"]["values"]
        except Exception as exc:
            logger.error("Gemini embedding failed: %s", exc)

        return self._embed_local_features(text)
