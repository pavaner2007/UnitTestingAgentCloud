"""
OllamaService — Compatibility wrapper that delegates to CloudLLMService.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.core.config import settings
from app.services.cloud_llm_service import get_cloud_llm_service

if TYPE_CHECKING:
    from app.agents.code_chunking_agent import CodeChunk

logger = logging.getLogger(__name__)


class OllamaService:
    """Wrapper that delegates summarization calls directly to CloudLLMService."""

    def __init__(self) -> None:
        self._cloud_service = get_cloud_llm_service()

    @property
    def _text_model(self) -> str:
        return settings.cloud_text_model

    @property
    def _code_model(self) -> str:
        return settings.cloud_code_model

    def _resolve_code_model(self) -> str:
        return settings.cloud_code_model

    def _generate(self, prompt: str, model: str | None = None, max_tokens: int = 2048) -> str | None:
        return self._cloud_service.complete(prompt, model=model, max_tokens=max_tokens)

    def is_available(self) -> bool:
        return self._cloud_service.is_available()

    def summarize_readme(self, readme_text: str) -> str | None:
        return self._cloud_service.summarize_readme(readme_text)

    def summarize_module(self, module_name: str, file_names: list[str]) -> str | None:
        return self._cloud_service.summarize_module(module_name, file_names)

    def summarize_code_chunk(self, chunk: CodeChunk) -> str | None:
        return self._cloud_service.summarize_code_chunk(chunk)

    def summarize_chunk(self, code_chunk: str, context: str = "") -> str | None:
        return self._cloud_service.summarize_chunk(code_chunk, context)
