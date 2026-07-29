from datetime import datetime, timezone
from sqlalchemy import DateTime, String, Text, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import PrimaryKeyConstraint


class Base(DeclarativeBase):
    pass


class AnalysisReportModel(Base):
    __tablename__ = "analysis_reports"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    repository_name: Mapped[str] = mapped_column(String(255), nullable=False)
    repository_url: Mapped[str] = mapped_column(Text, nullable=False)
    report_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class SummaryCacheModel(Base):
    """Content-addressed summary cache keyed by (content_hash, summary_type, model_used).

    The composite primary key means that upgrading a model (e.g. qwen2.5:7b →
    qwen2.5-coder:7b) naturally invalidates all old entries for that model — a lookup
    against the new model name simply misses and regenerates, instead of silently
    reusing a stale summary.
    """
    __tablename__ = "summary_cache"

    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    summary_type: Mapped[str] = mapped_column(String(50), nullable=False)   # 'chunk' | 'file' | 'module'
    model_used: Mapped[str] = mapped_column(String(100), nullable=False)    # exact model name
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("content_hash", "summary_type", "model_used", name="pk_summary_cache"),
    )


class ChunkEmbeddingModel(Base):
    """Stores chunk vector embeddings for Q&A similarity retrieval."""
    __tablename__ = "chunk_embeddings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    repo_analysis_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    chunk_content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_json: Mapped[str] = mapped_column(Text, nullable=False)
    start_line: Mapped[int] = mapped_column(nullable=False, default=1)
    end_line: Mapped[int] = mapped_column(nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
