import logging
from app.services.cloud_llm_service import get_cloud_llm_service

logger = logging.getLogger(__name__)


class GroqClient:
    """Thin wrapper delegating completions to CloudLLMService for multi-key rotation."""

    def __init__(self) -> None:
        self._cloud_service = get_cloud_llm_service()

    def complete(self, prompt: str, max_tokens: int = 2048) -> str | None:
        """Send a prompt to Groq (with dedicated report key or rotation) and return text response."""
        return self._cloud_service.complete(prompt, model="openai/gpt-oss-20b", max_tokens=max_tokens, task_type="report")
