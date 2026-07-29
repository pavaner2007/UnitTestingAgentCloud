from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AutoQA Agent"
    environment: str = "development"
    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/autoqa_agent"
    workspace_dir: str = "../repositories"
    reports_dir: str = "../reports"
    log_level: str = "INFO"
    groq_api_key: str | None = None
    groq_api_keys: str | None = None  # Comma-separated list of multiple Groq API keys for key rotation
    # Dedicated Groq API Keys by task type:
    groq_api_key_code: str | None = None    # Dedicated key for code chunk analysis (qwen-2.5-coder-32b)
    groq_api_key_text: str | None = None    # Dedicated key for README & module summaries (llama-3.3-70b-versatile)
    groq_api_key_report: str | None = None  # Dedicated key for high-level architecture reports
    groq_api_key_chat: str | None = None    # Dedicated key for interactive Q&A chat
    openai_api_key: str | None = None
    gemini_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434"

    # ── Email / SMTP settings ─────────────────────────────────────
    # Both must be set to enable the "Email Report" feature.
    # Use a Gmail App Password — NOT your normal Gmail password.
    email_sender_address: str | None = None
    email_sender_app_password: str | None = None

    # ── Cloud LLM & Embedding Settings ──────────────────────────────────────
    # Cloud providers: "groq", "openai", "gemini"
    cloud_llm_provider: str = "groq"
    cloud_embed_provider: str = "local"  # "local" (pure Python vector features), "openai", "gemini"

    # Cloud LLM Model Names
    cloud_text_model: str = "llama-3.3-70b-versatile"
    cloud_code_model: str = "llama-3.3-70b-versatile"
    cloud_embed_model: str = "text-embedding-3-small"

    # Cloud concurrency and timeout settings
    cloud_max_concurrency: int = 5
    cloud_chunk_timeout_seconds: int = 30

    # ── Legacy / Ollama fallback settings ────────────────────────────────────
    ollama_text_model: str = "llama3.1:8b"
    ollama_code_model: str = "qwen2.5-coder:7b"
    ollama_max_concurrency: int = 4
    ollama_chunk_timeout_seconds: int = 30
    ollama_batch_by_model: bool = True

    # ── File prioritization / budget settings ─────────────────────────────────
    # Hard cap on number of source files to deep-analyze per repository
    max_files_to_analyze: int = 25
    # Cap on max semantic chunks sent to local LLM for summarization per repo
    max_chunks_to_summarize: int = 15
    # Rough token budget (4 chars ≈ 1 token heuristic) for code analysis phase
    max_code_token_budget: int = 40000
    # Maximum characters per semantic code chunk sent to the code model
    code_chunk_max_chars: int = 3000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def groq_keys_list(self) -> list[str]:
        keys = []
        if self.groq_api_keys:
            for k in self.groq_api_keys.split(","):
                k_clean = k.strip()
                if k_clean and k_clean not in keys:
                    keys.append(k_clean)
        if self.groq_api_key:
            k_clean = self.groq_api_key.strip()
            if k_clean and k_clean not in keys:
                keys.append(k_clean)
        return keys

    @property
    def workspace_path(self) -> Path:
        return Path(self.workspace_dir).resolve()

    @property
    def reports_path(self) -> Path:
        return Path(self.reports_dir).resolve()


settings = Settings()
