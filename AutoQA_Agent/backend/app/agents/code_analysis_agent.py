"""
CodeAnalysisAgent — hierarchical map-reduce orchestrator for the local
code-analysis stage.

Pipeline executed by this agent
---------------------------------
  Phase 0 : File prioritization          (FilePrioritizationAgent)
  Phase 1 : Semantic chunking            (CodeChunkingAgent)
  Phase 2 : Pattern detection            (PatternDetector)   ← deterministic, no LLM
  Phase A : Code-model chunk summaries   (OllamaService / worker pool)
  Phase B : Text-model reduce            (OllamaService / worker pool)
            → file summaries             (chunk list → one summary per file)
            → module summaries           (file summaries → per-directory summary)
  Output  : CodeInsights

Model batching (OLLAMA_BATCH_BY_MODEL=True)
-------------------------------------------
  All Phase A calls complete before Phase B begins.  This prevents Ollama from
  alternating between two loaded models on constrained hardware, which would
  serialize the pipeline and negate the concurrency benefit.  If the user's
  hardware can hold both models in VRAM simultaneously, they may set
  OLLAMA_BATCH_BY_MODEL=False to allow interleaving.

Groq boundary guarantee
------------------------
  Only `module_summaries` and `notable_patterns` from CodeInsights are ever
  forwarded to Groq — NOT `file_summaries` or raw chunk content.
  See analysis_service.py for enforcement.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.agents.bug_detection_agent import BugDetectionAgent
from app.agents.code_chunking_agent import CodeChunk, CodeChunkingAgent
from app.agents.dependency_graph_agent import DependencyGraphAgent
from app.agents.file_prioritization_agent import FilePrioritizationAgent, PrioritizationResult, PrioritizedFile
from app.agents.pattern_detector import PatternDetector
from app.core.config import settings
from app.schemas.analysis import CodeInsights, DependencyGraph, TechStackResponse
from app.services.cache_service import CacheService, sha256_of
from app.services.ollama_service import OllamaService
from app.services.pipeline_status_service import pipeline_status
from app.services.worker_pool import run_concurrent

logger = logging.getLogger(__name__)

_SUMMARY_TYPE_CHUNK  = "chunk"
_SUMMARY_TYPE_FILE   = "file"
_SUMMARY_TYPE_MODULE = "module"


class CodeAnalysisAgent:
    """Hierarchical map-reduce code analysis orchestrator."""

    def __init__(self, db: Session) -> None:
        self._db          = db
        self._prioritizer = FilePrioritizationAgent()
        self._chunker     = CodeChunkingAgent()
        self._detector    = PatternDetector()
        self._bug_agent   = BugDetectionAgent(db)
        self._dep_agent   = DependencyGraphAgent()
        self._ollama      = OllamaService()
        self._cache       = CacheService(db)
        self.last_chunks_with_vecs: list[dict] = []

    # ── Public ────────────────────────────────────────────────────────────────

    def analyze(
        self,
        repo_path: Path,
        tech_stack: TechStackResponse | None = None,
        route_files: set[str] | None = None,
        analysis_id: str | None = None,
    ) -> CodeInsights:
        """
        Run the full hierarchical analysis and return CodeInsights.

        This method is synchronous — it drives an asyncio event loop internally
        so it can be called from the synchronous analysis_service pipeline.
        """
        try:
            return asyncio.run(self._async_analyze(repo_path, tech_stack, route_files, analysis_id))
        except RuntimeError:
            # Already inside an event loop (e.g. test environment)
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(
                    self._async_analyze(repo_path, tech_stack, route_files, analysis_id)
                )
            finally:
                loop.close()

    # ── Internal async pipeline ───────────────────────────────────────────────

    async def _async_analyze(
        self,
        repo_path: Path,
        tech_stack: TechStackResponse | None,
        route_files: set[str] | None,
        analysis_id: str | None = None,
    ) -> CodeInsights:
        def _st(stage: str, status: str, preview: str | None = None) -> None:
            if analysis_id:
                pipeline_status.set_status(analysis_id, stage, status, preview)

        # ── Phase 0: Prioritization ───────────────────────────────────────────
        logger.info("CodeAnalysis Phase 0: file prioritization")
        _st("File Prioritization", "running")
        prio_result: PrioritizationResult = self._prioritizer.prioritize(
            repo_path=repo_path,
            route_files=route_files or set(),
        )
        prioritized = prio_result.selected
        skipped_breakdown = prio_result.skipped_breakdown
        analyzed_files = [str(pf.path) for pf in prioritized]
        skipped_count = sum(skipped_breakdown.values())
        _st("File Prioritization", "done",
            f"{len(prioritized)} of {len(prioritized) + skipped_count} files selected")

        # ── Phase 1: Semantic chunking ────────────────────────────────────────
        logger.info("CodeAnalysis Phase 1: chunking %d files", len(prioritized))
        _st("Semantic Chunking", "running")
        all_chunks: list[CodeChunk] = []
        chunks_by_file: dict[str, list[CodeChunk]] = {}
        for pf in prioritized:
            file_chunks = self._chunker.chunk_file(pf.path, repo_path)
            all_chunks.extend(file_chunks)
            rel = str(pf.path.relative_to(repo_path))
            chunks_by_file[rel] = file_chunks

        logger.info("CodeAnalysis: %d chunks from %d files", len(all_chunks), len(prioritized))
        _st("Semantic Chunking", "done", f"{len(all_chunks)} AST chunks extracted")

        # ── Phase 1.5: Eager Embedding Generation ─────────────────────────────
        logger.info("CodeAnalysis Phase 1.5: generating embeddings for %d chunks", len(all_chunks))
        _st("Embedding Generation", "running")
        from app.services.embedding_service import EmbeddingService
        embed_svc = EmbeddingService(self._db)
        chunks_with_vecs: list[dict] = []
        for ch in all_chunks:
            vec = embed_svc.embed_text(ch.content)
            if vec:
                chunks_with_vecs.append({
                    "file_path": ch.file_path,
                    "content": ch.content,
                    "start_line": ch.start_line,
                    "end_line": ch.end_line,
                    "embedding": vec,
                })
        self.last_chunks_with_vecs = chunks_with_vecs
        logger.info("CodeAnalysis Phase 1.5: %d chunk embeddings ready", len(chunks_with_vecs))
        _st("Embedding Generation", "done", f"{len(chunks_with_vecs)} embeddings generated")

        # ── Phase 2: Pattern detection + Bug detection ──────────────────────
        logger.info("CodeAnalysis Phase 2: pattern detection")
        _st("Pattern Detection", "running")
        notable_patterns = self._detector.detect_in_files(
            file_paths=[pf.path for pf in prioritized],
            repo_root=repo_path,
        )
        # Also scan chunks for finer context
        chunk_patterns = self._detector.detect_in_chunks(all_chunks)
        # Merge and deduplicate
        pattern_set = dict.fromkeys(notable_patterns + chunk_patterns)
        notable_patterns = list(pattern_set.keys())
        _st("Pattern Detection", "done", f"{len(notable_patterns)} patterns found")

        logger.info("CodeAnalysis Phase 2: bug detection")
        _st("Bug Detection", "running")
        issues, issues_summary = self._bug_agent.detect(
            repo_path=repo_path,
            prioritized_files=prioritized,
        )
        bug_preview = f"{len(issues)} issues detected"
        if not issues and issues_summary.get("ruff_skipped"):
            bug_preview = "ruff skipped (using static smells)"
        _st("Bug Detection", "done", bug_preview)

        logger.info("CodeAnalysis Phase 2: dependency graph (full-repo scan)")
        _st("Dependency Graph", "running")
        dep_graph_raw = self._dep_agent.build_graph(
            repo_path=repo_path,
            # file_paths not passed — agent scans ALL source files independently
            # of the LLM budget, since import parsing has zero LLM cost.
        )
        dependency_graph = DependencyGraph(**dep_graph_raw)
        _st("Dependency Graph", "done",
            f"{len(dependency_graph.nodes)} nodes, {len(dependency_graph.edges)} edges")

        # ── Phase A: Code-model chunk summaries ───────────────────────────────
        logger.info("CodeAnalysis Phase A: %d chunk summaries (code model)", len(all_chunks))
        _st("Chunk Summarization", "running")
        chunk_summaries = await self._summarize_chunks(all_chunks)

        # Cache hit tracking
        total_lookups = len(all_chunks)
        hits = sum(1 for s in chunk_summaries if s and s.startswith("__cached__"))
        # Strip the internal marker
        chunk_summaries = [
            s.lstrip("__cached__") if s and s.startswith("__cached__") else s
            for s in chunk_summaries
        ]
        cache_hit_rate = (hits / total_lookups) if total_lookups > 0 else 0.0

        # Map chunk summaries back to chunks
        chunk_to_summary: dict[int, str] = {
            i: (chunk_summaries[i] or "")
            for i in range(len(all_chunks))
        }

        # ── Phase B: Text-model reduce ────────────────────────────────────────
        logger.info("CodeAnalysis Phase B: file + module reduce (text model)")
        _st("Chunk Summarization", "done",
            f"{len(all_chunks)} chunks ({int(cache_hit_rate * 100)}% cached)")
        _st("Module & File Reduce", "running")
        file_summaries: dict[str, str] = {}
        for rel_path, file_chunks in chunks_by_file.items():
            if not file_chunks:
                continue
            # Collect summaries for this file's chunks
            chunk_indices = [
                i for i, ch in enumerate(all_chunks) if ch.file_path == rel_path
            ]
            summaries = [chunk_to_summary[i] for i in chunk_indices if chunk_to_summary.get(i)]

            if not summaries:
                continue

            if len(summaries) <= 3:
                # Deterministic bullet join — no LLM call
                file_summaries[rel_path] = " | ".join(
                    f"{all_chunks[chunk_indices[j]].name}: {s}"
                    for j, s in enumerate(summaries)
                    if s
                )
            else:
                # LLM reduce call via text model
                file_sum = await self._reduce_file(rel_path, summaries)
                if file_sum:
                    file_summaries[rel_path] = file_sum

        # Module summaries: group file summaries by top-level directory
        module_summaries: dict[str, str] = await self._reduce_modules(
            file_summaries, repo_path
        )

        logger.info(
            "CodeAnalysis complete: %d files, %d modules, cache_hit_rate=%.0f%%",
            len(file_summaries), len(module_summaries), cache_hit_rate * 100,
        )
        _st("Module & File Reduce", "done",
            f"{len(file_summaries)} files, {len(module_summaries)} modules summarized")

        return CodeInsights(
            analyzed_files=analyzed_files,
            skipped_files_count=skipped_count,
            skipped_files_breakdown=skipped_breakdown,
            file_summaries=file_summaries,
            module_summaries=module_summaries,
            notable_patterns=notable_patterns,
            cache_hit_rate=round(cache_hit_rate, 3),
            issues=issues,
            issues_summary=issues_summary,
            dependency_graph=dependency_graph,
        )

    # ── Phase A helpers ───────────────────────────────────────────────────────

    async def _summarize_chunks(self, chunks: list[CodeChunk]) -> list[str | None]:
        """Summarize chunks via code model, enforcing max_chunks_to_summarize cap for uncached LLM calls."""
        # Use the resolved model name (may be fallback text model if code model not pulled)
        code_model = self._ollama._resolve_code_model()
        pool_timeout = float(settings.ollama_chunk_timeout_seconds) + 15.0
        max_llm_chunks = getattr(settings, "max_chunks_to_summarize", 15)

        uncached_count = 0

        async def _summarize_one(chunk: CodeChunk) -> str | None:
            nonlocal uncached_count
            content_hash = sha256_of(chunk.content)

            # Cap uncached LLM calls to prevent slow runs
            if uncached_count >= max_llm_chunks:
                return f"{chunk.chunk_type.title()} `{chunk.name}` in {chunk.file_path}"

            uncached_count += 1
            # LLM call (synchronous Ollama wrapped in executor)
            loop = asyncio.get_running_loop()
            summary = await loop.run_in_executor(
                None, self._ollama.summarize_code_chunk, chunk
            )
            if summary is None:
                # Heuristic fallback — never None in the final result
                summary = f"{chunk.chunk_type.title()} `{chunk.name}` in {chunk.file_path} (summary unavailable)"
            else:
                self._cache.set_cached(content_hash, _SUMMARY_TYPE_CHUNK, summary, code_model)
            return summary

        def _fallback(index: int, exc: Exception) -> str:
            chunk = chunks[index]
            return f"{chunk.chunk_type.title()} `{chunk.name}` in {chunk.file_path} (timed out)"

        tasks = [_summarize_one(chunk) for chunk in chunks]
        return await run_concurrent(
            tasks,
            max_concurrency=settings.ollama_max_concurrency,
            timeout_seconds=pool_timeout,
            fallback_fn=_fallback,
        )

    # ── Phase B helpers ───────────────────────────────────────────────────────

    async def _reduce_file(self, rel_path: str, chunk_summaries: list[str]) -> str | None:
        """LLM reduce: list of chunk summaries → one file-level summary (text model)."""
        combined = "\n".join(f"- {s}" for s in chunk_summaries[:10])
        prompt = (
            f"You are a code reviewer. The following are summaries of the key functions/classes "
            f"in the file `{rel_path}`:\n{combined}\n\n"
            "In one sentence, summarise what this file's overall responsibility is. "
            "Do not list the functions. Answer with only the sentence."
        )
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._ollama._generate(prompt, model=self._ollama._text_model, max_tokens=80)
        )

    async def _reduce_modules(
        self,
        file_summaries: dict[str, str],
        repo_path: Path,
    ) -> dict[str, str]:
        """Group file summaries by top-level directory and produce module summaries."""
        module_files: dict[str, list[str]] = {}
        for rel_path, summary in file_summaries.items():
            parts = Path(rel_path).parts
            module_dir = parts[0] if len(parts) > 1 else "_root"
            module_files.setdefault(module_dir, []).append(f"{rel_path}: {summary}")

        module_summaries: dict[str, str] = {}

        for module_name, file_lines in module_files.items():
            if not file_lines:
                continue
            # For small modules use the text model; fall back to joining if offline
            loop = asyncio.get_event_loop()
            summary = await loop.run_in_executor(
                None,
                lambda mn=module_name, fl=file_lines: self._ollama.summarize_module(
                    mn, [line.split(":")[0] for line in fl[:20]]
                )
            )
            if summary:
                module_summaries[module_name] = summary
            else:
                module_summaries[module_name] = "; ".join(file_lines[:3])

        return module_summaries
