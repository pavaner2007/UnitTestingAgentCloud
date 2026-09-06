"""
CloudLLMService — Unified client for Cloud LLM completions with Task-Dedicated API Key routing & Groq Key Rotation.

Features:
  - Task-Dedicated Groq API Keys:
      * task_type="code"   -> GROQ_API_KEY_CODE (qwen-2.5-coder-32b)
      * task_type="text"   -> GROQ_API_KEY_TEXT (llama-3.3-70b-versatile)
      * task_type="report" -> GROQ_API_KEY_REPORT (high-level synthesis)
      * task_type="chat"   -> GROQ_API_KEY_CHAT (Q&A RAG chat)
  - Automatic fallback to round-robin rotation across `GROQ_API_KEYS` / `GROQ_API_KEY`.
  - Automatic rate-limit failover (HTTP 429).
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING
import httpx

from app.core.config import settings

if TYPE_CHECKING:
    from app.agents.code_chunking_agent import CodeChunk

logger = logging.getLogger(__name__)

# Module-level singleton
_cloud_llm_service_singleton: "CloudLLMService | None" = None


def get_cloud_llm_service() -> "CloudLLMService":
    """Return (or create) the process-wide CloudLLMService singleton."""
    global _cloud_llm_service_singleton
    if _cloud_llm_service_singleton is None:
        _cloud_llm_service_singleton = CloudLLMService()
    return _cloud_llm_service_singleton


class CloudLLMService:
    """Multi-provider Cloud LLM service with Task-Dedicated API Keys & Round-Robin failover."""

    def __init__(self) -> None:
        self.provider = (settings.cloud_llm_provider or "groq").lower().strip()
        self.text_model = settings.cloud_text_model
        self.code_model = settings.cloud_code_model
        self.timeout = float(settings.cloud_chunk_timeout_seconds)

        self._groq_key_index = 0
        self._openai_client = None
        self._gemini_client = None

        self._init_provider_clients()

    def _init_provider_clients(self) -> None:
        keys = settings.groq_keys_list
        if keys:
            logger.info("CloudLLMService initialized with %d Groq API key(s).", len(keys))
        if settings.groq_api_key_code:
            logger.info("CloudLLMService: Dedicated Groq key active for CODE tasks.")
        if settings.groq_api_key_text:
            logger.info("CloudLLMService: Dedicated Groq key active for TEXT tasks.")
        if settings.groq_api_key_report:
            logger.info("CloudLLMService: Dedicated Groq key active for REPORT tasks.")
        if settings.groq_api_key_chat:
            logger.info("CloudLLMService: Dedicated Groq key active for CHAT tasks.")

    def is_available(self) -> bool:
        """Check if any valid API keys are configured."""
        if self.provider == "groq":
            return bool(
                settings.groq_keys_list
                or settings.groq_api_key_code
                or settings.groq_api_key_text
                or settings.groq_api_key_report
                or settings.groq_api_key_chat
            )
        elif self.provider == "openai":
            return bool(settings.openai_api_key or self._openai_client)
        elif self.provider == "gemini":
            return bool(settings.gemini_api_key or self._gemini_client)
        return bool(settings.groq_keys_list or settings.openai_api_key or settings.gemini_api_key)

    def _get_dedicated_groq_key(self, task_type: str | None) -> str | None:
        """Return dedicated API key for task_type if configured."""
        if not task_type:
            return None
        t = task_type.lower().strip()
        if t == "code" and settings.groq_api_key_code:
            return settings.groq_api_key_code.strip()
        if t == "text" and settings.groq_api_key_text:
            return settings.groq_api_key_text.strip()
        if t in ("report", "reasoning") and settings.groq_api_key_report:
            return settings.groq_api_key_report.strip()
        if t == "chat" and settings.groq_api_key_chat:
            return settings.groq_api_key_chat.strip()
        return None

    def _get_next_groq_key(self) -> str | None:
        keys = settings.groq_keys_list
        if not keys:
            return None
        key = keys[self._groq_key_index % len(keys)]
        self._groq_key_index += 1
        return key

    def complete(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int = 2048,
        system_prompt: str | None = None,
        task_type: str | None = None,
    ) -> str | None:
        """Generate LLM completion using dedicated task key or round-robin rotation."""
        if not prompt or not prompt.strip():
            return None

        model_name = model or self.text_model

        if self.provider == "groq" or self.is_available():
            return self._complete_groq(prompt, model_name, max_tokens, system_prompt, task_type)
        elif self.provider == "openai":
            return self._complete_openai(prompt, model_name, max_tokens, system_prompt)
        elif self.provider == "gemini":
            return self._complete_gemini(prompt, model_name, max_tokens, system_prompt)

        return self._complete_groq(prompt, model_name, max_tokens, system_prompt, task_type)

    def summarize_readme(self, readme_text: str) -> str | None:
        if not readme_text or not readme_text.strip():
            return None
        truncated = readme_text[:8000]
        prompt = (
            "You are a technical documentation expert. Read the following README and produce a "
            "concise 3–4 sentence summary describing: what the project does, its primary purpose, "
            "and its key architecture/target users. Base your answer strictly on the text.\n\n"
            f"README:\n{truncated}\n\nSummary:"
        )
        return self.complete(prompt, model=self.text_model, max_tokens=300, task_type="text")

    def summarize_module(self, module_name: str, file_names: list[str]) -> str | None:
        if not file_names:
            return None
        files_str = ", ".join(file_names[:30])
        prompt = (
            f"You are a senior software architect. "
            f"The module/directory '{module_name}' contains these files: {files_str}. "
            f"In one concise sentence, describe what this module is responsible for."
        )
        return self.complete(prompt, model=self.text_model, max_tokens=100, task_type="text")

    def summarize_code_chunk(self, chunk: CodeChunk) -> str | None:
        if not chunk.content or not chunk.content.strip():
            return None

        prompt = (
            f"You are a senior code reviewer. Below is a {chunk.chunk_type} named `{chunk.name}` "
            f"from file `{chunk.file_path}` (lines {chunk.start_line}–{chunk.end_line}).\n\n"
            "In 2–3 concise sentences, describe:\n"
            "1. What this code does.\n"
            "2. Its key inputs/outputs.\n"
            "3. Notable patterns (auth, DB, APIs, security operations).\n\n"
            f"```\n{chunk.content[:3000]}\n```\n\nSummary:"
        )
        return self.complete(prompt, model=self.code_model, max_tokens=150, task_type="code")

    def summarize_chunk(self, code_chunk: str, context: str = "") -> str | None:
        if not code_chunk or not code_chunk.strip():
            return None
        ctx = f"Context: {context}\n\n" if context else ""
        prompt = (
            f"{ctx}Summarise what the following code does in one sentence.\n\n"
            f"```\n{code_chunk[:3000]}\n```\n\nSummary:"
        )
        return self.complete(prompt, model=self.text_model, max_tokens=80, task_type="code")

    # ── Groq Multi-Key & Task-Dedicated Completion Router ─────────────────────

    def _complete_groq(
        self,
        prompt: str,
        model: str,
        max_tokens: int,
        system_prompt: str | None,
        task_type: str | None = None,
    ) -> str | None:
        # 1. Candidate models: requested model first, then openai/gpt-oss-20b as rate-limit failover
        requested_model = model or "openai/gpt-oss-20b"
        candidate_models = [requested_model]
        if task_type == "chat" and "openai/gpt-oss-20b" not in candidate_models:
            candidate_models.insert(0, "openai/gpt-oss-20b")
        elif "openai/gpt-oss-20b" not in candidate_models:
            candidate_models.append("openai/gpt-oss-20b")

        # 2. Candidate keys: dedicated task key first, then general pool
        dedicated_key = self._get_dedicated_groq_key(task_type)
        candidate_keys = []
        if dedicated_key:
            candidate_keys.append(dedicated_key)

        for k in settings.groq_keys_list:
            if k not in candidate_keys:
                candidate_keys.append(k)

        if not candidate_keys:
            logger.warning("No Groq API keys available for task_type=%s.", task_type)
            return None

        # 3. Try model candidates x key candidates
        for m in candidate_models:
            for key in candidate_keys:
                try:
                    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
                    messages = []
                    if system_prompt:
                        messages.append({"role": "system", "content": system_prompt})
                    messages.append({"role": "user", "content": prompt})

                    payload = {
                        "model": m,
                        "messages": messages,
                        "max_tokens": max_tokens,
                    }
                    resp = httpx.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        json=payload,
                        headers=headers,
                        timeout=self.timeout,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        return data["choices"][0]["message"]["content"].strip()
                    elif resp.status_code in (429, 401, 403, 400, 404):
                        logger.warning(
                            "Groq API error (%d) for model=%s, task_type=%s — attempting next candidate key/model.",
                            resp.status_code,
                            m,
                            task_type,
                        )
                        continue
                    else:
                        logger.warning("Groq API HTTP error %d for model=%s: %s", resp.status_code, m, resp.text)
                except Exception as exc:
                    logger.warning("Groq completion exception for model=%s, task_type=%s: %s", m, task_type, exc)

        return None

    def _complete_openai(
        self, prompt: str, model: str, max_tokens: int, system_prompt: str | None
    ) -> str | None:
        key = settings.openai_api_key
        if not key:
            return None
        try:
            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            payload = {
                "model": model or "gpt-4o-mini",
                "messages": messages,
                "max_tokens": max_tokens,
            }
            resp = httpx.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            logger.warning("OpenAI completion failed: %s", exc)
        return None

    def _complete_gemini(
        self, prompt: str, model: str, max_tokens: int, system_prompt: str | None
    ) -> str | None:
        key = settings.gemini_api_key
        if not key:
            return None
        try:
            target_model = model if ("gemini" in model) else "gemini-1.5-flash"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent?key={key}"
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            resp = httpx.post(url, json=payload, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as exc:
            logger.warning("Gemini completion failed: %s", exc)
        return None
