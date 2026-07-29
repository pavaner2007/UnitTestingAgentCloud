"""
RepositoryAnalysisService — orchestrates the full analysis pipeline.

Pipeline
--------
  1.  Clone repository
  2.  Deterministic tech stack detection (TechStackDetectionAgent)
  3.  Deterministic API discovery (ApiDiscoveryAgent)
  4.  Hierarchical code analysis (CodeAnalysisAgent)   ← NEW
      · File prioritization → semantic chunking → pattern detection
      · Phase A: concurrent code-model chunk summaries
      · Phase B: text-model reduce → file + module summaries
      · Produces CodeInsights (file_summaries, module_summaries, notable_patterns)
      · Degradation: if this stage fails, pipeline continues with code_insights=null
  5.  README summarisation via Ollama (text model)
  6.  Module summarisation via Ollama (text model)
      → replaced/enriched by CodeInsights.module_summaries when available
  7.  Build structured facts (no raw code, only facts + summaries)
      GROQ BOUNDARY: module_summaries + notable_patterns from CodeInsights are
      passed to Groq. file_summaries and raw chunk content are NEVER forwarded.
  8.  Groq high-level reasoning → enriched analysis
  9.  Assemble final RepositoryAnalysisReport
  10. Persist to DB + JSON file
"""
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.agents.api_discovery_agent import ApiDiscoveryAgent
from app.agents.code_analysis_agent import CodeAnalysisAgent
from app.agents.report_generation_agent import ReportGenerationAgent
from app.agents.repository_analysis_agent import RepositoryAnalysisAgent
from app.agents.tech_stack_agent import TechStackDetectionAgent
from app.core.exceptions import AnalysisNotFoundException
from app.repositories.analysis_repository import AnalysisRepository
from app.schemas.analysis import CodeInsights, DetectedFeature, RepositoryAnalysisReport
from app.services.groq_service import GroqAnalysisService
from app.services.ollama_service import OllamaService
from app.services.pipeline_status_service import pipeline_status

logger = logging.getLogger(__name__)

_IGNORED_TOP_LEVEL = {
    ".git", "node_modules", "venv", ".venv", "dist", "build",
    "target", "__pycache__", ".github", ".idea", ".vscode",
    "coverage", ".pytest_cache", "htmlcov",
}
_README_NAMES = {"README.md", "README.rst", "README.txt", "README", "readme.md"}

# Max serialized bytes in the Groq facts payload (regression guard)
_GROQ_PAYLOAD_MAX_BYTES = 32_768


class RepositoryAnalysisService:
    def __init__(self, db: Session) -> None:
        self.db                  = db
        self.repository_agent    = RepositoryAnalysisAgent()
        self.tech_stack_agent    = TechStackDetectionAgent()
        self.api_discovery_agent = ApiDiscoveryAgent()
        self.code_analysis_agent = CodeAnalysisAgent(db)
        self.report_generation_agent = ReportGenerationAgent()
        self.analysis_repository = AnalysisRepository(db)
        self.ollama = OllamaService()
        self.groq   = GroqAnalysisService()

    # ── Public API ────────────────────────────────────────────────────────────

    def analyze_repository(self, github_url: str, analysis_id: str | None = None) -> RepositoryAnalysisReport:
        """Run the full analysis pipeline for a GitHub URL and return the report."""
        logger.info("Starting repository analysis for %s", github_url)

        _id = analysis_id or "unknown"

        def _status(stage: str, status: str, preview: str | None = None) -> None:
            """Emit a pipeline status update if we have an analysis_id."""
            if analysis_id:
                pipeline_status.set_status(analysis_id, stage, status, preview)

        try:
            # ── Steps 1-3: Deterministic analysis ────────────────────────────────
            _status("Clone Repo", "running")
            local_path   = self.repository_agent.clone_repository(github_url)
            metadata     = self.repository_agent.extract_metadata(github_url, local_path)
            _status("Clone Repo", "done",
                    f"{metadata.total_files} files, {metadata.total_directories} dirs")

            _status("Tech Stack Detection", "running")
            tech_stack   = self.tech_stack_agent.detect(local_path)
            stack_preview = ", ".join(
                (tech_stack.frontend + tech_stack.backend + tech_stack.databases)[:4]
            ) or "detected"
            _status("Tech Stack Detection", "done", stack_preview)

            _status("API Discovery", "running")
            api_inventory = self.api_discovery_agent.discover(local_path)
            _status("API Discovery", "done", f"{len(api_inventory)} endpoints found")

            # Collect file paths known to contain routes (priority boost)
            route_files: set[str] = {ep.file for ep in api_inventory if ep.file}

            # ── Step 4: Hierarchical code analysis (graceful degradation) ─────────
            code_insights: CodeInsights | None = None
            try:
                logger.info("Starting hierarchical code analysis")
                code_insights = self.code_analysis_agent.analyze(
                    repo_path=local_path,
                    tech_stack=tech_stack,
                    route_files=route_files,
                    analysis_id=analysis_id,
                )
                logger.info(
                    "Code analysis complete: %d files analyzed, cache_hit_rate=%.0f%%",
                    len(code_insights.analyzed_files),
                    code_insights.cache_hit_rate * 100,
                )
            except Exception as exc:
                logger.warning(
                    "Code analysis stage failed (%s) — continuing with code_insights=null. "
                    "Report will still be generated using README/module-summary path.",
                    exc,
                )
                # Mark sub-phases failed if code analysis blew up entirely
                for stage in ["File Prioritization", "Semantic Chunking", "Embedding Generation",
                               "Pattern Detection", "Bug Detection", "Dependency Graph",
                               "Chunk Summarization", "Module & File Reduce"]:
                    _status(stage, "failed", "code analysis failed")

            # ── Step 5: README summarisation via Ollama ───────────────────────────
            readme_summary = self._summarize_readme(local_path)

            # ── Step 6: Module summarisation ──────────────────────────────────────
            # Use enriched summaries from code analysis when available; fall back to
            # filename-only Ollama summaries otherwise.
            if code_insights and code_insights.module_summaries:
                module_summaries = code_insights.module_summaries
            else:
                module_summaries = self._summarize_modules(local_path)

            # ── Step 7: Build structured facts (GROQ BOUNDARY) ───────────────────
            structured_facts = self._build_groq_facts(
                metadata=metadata,
                tech_stack=tech_stack,
                api_inventory=api_inventory,
                module_summaries=module_summaries,
                readme_summary=readme_summary,
                code_insights=code_insights,
            )

            # ── Step 8: Groq high-level reasoning ────────────────────────────────
            _status("Groq AI Reasoning", "running")
            logger.info("Sending structured facts to Groq for reasoning")
            ai_result = self.groq.generate_report(structured_facts)
            confidence = ai_result.get("confidence_score")
            _status("Groq AI Reasoning", "done",
                    f"Confidence: {int(confidence)}%" if confidence else "done")

            # ── Step 9: V2 Enterprise Agents Execution ────────────────────────────
            _status("Change Impact Analysis", "running")
            from app.agents.change_impact_agent import ChangeImpactAnalysisAgent
            impact_agent = ChangeImpactAnalysisAgent()
            # Initial impact analysis for root/entry file if available
            sample_file = (code_insights.analyzed_files[0] if code_insights and code_insights.analyzed_files else "main.py")
            impact_result = impact_agent.analyze_impact(
                target_file=sample_file,
                dependency_graph=code_insights.dependency_graph.model_dump() if code_insights and code_insights.dependency_graph else None,
                api_inventory=[ep.model_dump() for ep in api_inventory],
            )
            _status("Change Impact Analysis", "done", f"Sample impact: {impact_result.risk_level}")

            _status("Architecture Drift Audit", "running")
            from app.agents.architecture_drift_agent import ArchitectureDriftAgent
            drift_agent = ArchitectureDriftAgent()
            drift_report = drift_agent.audit(
                dependency_graph=code_insights.dependency_graph.model_dump() if code_insights and code_insights.dependency_graph else None,
                api_inventory=[ep.model_dump() for ep in api_inventory],
                tech_stack=tech_stack.model_dump() if tech_stack else None,
                analyzed_files=code_insights.analyzed_files if code_insights else None,
            )
            _status("Architecture Drift Audit", "done", f"{drift_report.total_violations} violations found")

            # ── Step 10: Assemble final report ────────────────────────────────────
            base_report = self.report_generation_agent.generate(
                metadata, tech_stack, api_inventory
            )

            detected_features = [
                DetectedFeature(
                    name=f.get("name", "Unknown"),
                    evidence=f.get("evidence", []),
                )
                for f in ai_result.get("detected_features", [])
                if isinstance(f, dict)
            ]

            report = base_report.model_copy(
                update={
                    "readme_summary": readme_summary,
                    "module_summaries": module_summaries,
                    "ai_explanation": {
                        "project_overview": ai_result.get("project_overview"),
                        "use_case":         ai_result.get("use_case"),
                        "complexity_level": ai_result.get("complexity_level"),
                        "workflow":         ai_result.get("workflow", []),
                        "key_technologies": ai_result.get("key_technologies", {}),
                        "api_summary":      ai_result.get("api_summary"),
                    },
                    "detected_features": detected_features,
                    "architecture_notes": ai_result.get("architecture_notes"),
                    "workflow":           ai_result.get("workflow", []),
                    "confidence_score":   ai_result.get("confidence_score"),
                    "code_insights":      code_insights,
                    "dependency_graph":   code_insights.dependency_graph if code_insights else None,
                    "architecture_drift": drift_report.model_dump(),
                }
            )

            # Post-report V2 agents that use report.model_dump()
            report_dict = report.model_dump()

            _status("Developer Onboarding Guide", "running")
            from app.agents.project_onboarding_agent import AIProjectOnboardingAgent
            onboarding_agent = AIProjectOnboardingAgent()
            onboarding_report = onboarding_agent.generate_onboarding(report_dict)
            _status("Developer Onboarding Guide", "done", f"{len(onboarding_report.recommended_reading_path)} steps, {len(onboarding_report.quizzes)} quizzes")

            _status("Repository Health Scoring", "running")
            from app.agents.repository_health_agent import RepositoryHealthScoreAgent
            health_agent = RepositoryHealthScoreAgent()
            health_report = health_agent.calculate_health(report_dict, drift_report.model_dump())
            _status("Repository Health Scoring", "done", f"Overall Score: {health_report.overall_score}/100")

            _status("Tech Debt Prioritization", "running")
            from app.agents.technical_debt_agent import TechnicalDebtPrioritizationAgent
            debt_agent = TechnicalDebtPrioritizationAgent()
            debt_report = debt_agent.prioritize_debt(report_dict, drift_report.model_dump())
            _status("Tech Debt Prioritization", "done", f"{debt_report.total_debt_items} items ranked")

            # Attach final V2 dictionaries to report
            report = report.model_copy(
                update={
                    "project_onboarding": onboarding_report.model_dump(),
                    "repository_health": health_report.model_dump(),
                    "technical_debt": debt_report.model_dump(),
                }
            )

            # ── Step 10: Persist ─────────────────────────────────────────────────
            # If the caller supplied an analysis_id (async path), override the
            # report's auto-generated UUID so DB key == polling key == frontend's
            # currentAnalysisId.  Without this, GET /analysis/{id} returns 404
            # because the report was saved under a different UUID.
            if analysis_id:
                report = report.model_copy(update={"analysis_id": analysis_id})

            if code_insights and hasattr(self.code_analysis_agent, 'last_chunks_with_vecs'):
                from app.services.vector_search_service import VectorSearchService
                vec_svc = VectorSearchService(self.db)
                vec_svc.store_chunk_embeddings(report.analysis_id, self.code_analysis_agent.last_chunks_with_vecs)

            self.report_generation_agent.save_json_report(report)
            self.analysis_repository.save(
                analysis_id=report.analysis_id,
                repository_name=report.repository_name,
                repository_url=report.repository_url,
                report_json=report.model_dump(),
            )
            logger.info(
                "Analysis complete: %s (confidence: %.0f%%)",
                report.analysis_id,
                report.confidence_score or 0,
            )
            return report

        except Exception as exc:
            logger.exception("Pipeline failed for %s", _id)
            if analysis_id:
                pipeline_status.fail_remaining(analysis_id, f"Pipeline error: {type(exc).__name__}")
            raise

    def get_analysis(self, analysis_id: str) -> dict:
        model = self.analysis_repository.get_by_id(analysis_id)
        if not model:
            raise AnalysisNotFoundException(f"Analysis not found: {analysis_id}")
        return model.report_json

    def get_analyses(self, limit: int = 50) -> list[dict]:
        """Return a lightweight summary list of all past analyses (newest first)."""
        rows = self.analysis_repository.list_all(limit=limit)
        results = []
        for row in rows:
            rj = row.report_json or {}
            results.append({
                "analysis_id":            row.id,
                "repository_name":        row.repository_name,
                "repository_url":         row.repository_url,
                "created_at":             row.created_at.isoformat() if row.created_at else None,
                "confidence_score":       rj.get("confidence_score"),
                "technology_stack":       rj.get("technology_stack", {}),
                "number_of_files":        rj.get("number_of_files"),
                "number_of_apis_discovered": rj.get("number_of_apis_discovered"),
            })
        return results

    # ── Private helpers ───────────────────────────────────────────────────────

    def _build_groq_facts(
        self,
        metadata,
        tech_stack,
        api_inventory,
        module_summaries: dict,
        readme_summary: str | None,
        code_insights: CodeInsights | None,
    ) -> dict:
        """
        Build the structured-facts payload for Groq.

        GROQ BOUNDARY — enforced here:
        - module_summaries (str values) → OK to forward
        - notable_patterns (str list)   → OK to forward
        - file_summaries                → NEVER forwarded
        - raw chunk content             → NEVER forwarded
        """
        facts: dict = {
            "repository_name": metadata.repository_name,
            "frontend":        tech_stack.frontend,
            "backend":         tech_stack.backend,
            "databases":       tech_stack.databases,
            "languages":       tech_stack.languages,
            "frameworks":      tech_stack.frameworks,
            "apis": [
                {
                    "method":    ep.method,
                    "path":      ep.path,
                    "framework": ep.framework,
                    "file":      ep.file,
                }
                for ep in api_inventory
            ],
            "modules": [
                {"name": name, "summary": summary}
                for name, summary in module_summaries.items()
                if summary
            ],
            "readme_summary":  readme_summary,
            "important_files": metadata.important_files[:15],
            "total_files":     metadata.total_files,
            "total_dirs":      metadata.total_directories,
        }

        # Append notable_patterns from code analysis (structured strings only)
        if code_insights and code_insights.notable_patterns:
            facts["notable_patterns"] = code_insights.notable_patterns[:30]

        # Append issues_summary (counts only — no file/line/message detail)
        # GROQ BOUNDARY: only the count dict is forwarded; full `issues` list is never sent
        if code_insights and code_insights.issues_summary:
            facts["issues_summary"] = code_insights.issues_summary

        # Payload size guard — log a warning if approaching the regression-test cap
        import json as _json
        payload_size = len(_json.dumps(facts, ensure_ascii=False).encode("utf-8"))
        if payload_size > _GROQ_PAYLOAD_MAX_BYTES:
            logger.warning(
                "Groq payload size %d bytes exceeds %d byte guard — "
                "check for accidental raw-code leakage. "
                "Actual payload size should be reported back to confirm/adjust the cap.",
                payload_size, _GROQ_PAYLOAD_MAX_BYTES,
            )
        else:
            logger.debug("Groq payload size: %d bytes (within %d byte cap)", payload_size, _GROQ_PAYLOAD_MAX_BYTES)

        return facts

    def _summarize_readme(self, repo_path: Path) -> str | None:
        """Find and summarise the README via Ollama."""
        for name in _README_NAMES:
            readme_path = repo_path / name
            if readme_path.exists() and readme_path.is_file():
                try:
                    text = readme_path.read_text(encoding="utf-8", errors="ignore")
                    if text.strip():
                        logger.info("Summarising README via Ollama (%d chars)", len(text))
                        return self.ollama.summarize_readme(text)
                except Exception as exc:
                    logger.warning("Failed to read README: %s", exc)
        logger.info("No README found in repository root")
        return None

    def _summarize_modules(self, repo_path: Path) -> dict[str, str]:
        """Fallback module summariser (used when code analysis is unavailable)."""
        summaries: dict[str, str] = {}
        try:
            top_level_dirs = [
                p for p in repo_path.iterdir()
                if p.is_dir() and p.name not in _IGNORED_TOP_LEVEL
            ]
        except Exception:
            return summaries

        for module_dir in sorted(top_level_dirs)[:12]:
            try:
                file_names = [
                    f.name for f in module_dir.rglob("*")
                    if f.is_file() and f.name not in {"__pycache__"}
                    and not any(part in _IGNORED_TOP_LEVEL for part in f.parts)
                ][:40]

                if not file_names:
                    continue

                logger.info("Summarising module '%s' via Ollama", module_dir.name)
                summary = self.ollama.summarize_module(module_dir.name, file_names)
                if summary:
                    summaries[module_dir.name] = summary
            except Exception as exc:
                logger.warning("Module summarisation failed for %s: %s", module_dir.name, exc)

        return summaries
