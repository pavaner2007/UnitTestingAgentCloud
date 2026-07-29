import json
import logging
import uuid
from pathlib import Path

from app.core.config import settings
from app.schemas.analysis import ApiEndpoint, ProjectStructureSummary, RepositoryAnalysisReport, TechStackResponse
from app.agents.repository_analysis_agent import RepositoryMetadata

logger = logging.getLogger(__name__)


class ReportGenerationAgent:
    """Assembles the base RepositoryAnalysisReport from deterministic facts.

    No AI calls happen here. AI enrichment (Ollama + Groq) is orchestrated
    by RepositoryAnalysisService before/after this agent runs.
    """

    def generate(
        self,
        metadata: RepositoryMetadata,
        tech_stack: TechStackResponse,
        api_inventory: list[ApiEndpoint],
    ) -> RepositoryAnalysisReport:
        analysis_id = str(uuid.uuid4())
        summary = ProjectStructureSummary(
            directories=metadata.total_directories,
            files=metadata.total_files,
            top_level_items=metadata.top_level_items,
            important_files=metadata.important_files,
        )

        return RepositoryAnalysisReport(
            analysis_id=analysis_id,
            repository_name=metadata.repository_name,
            repository_url=metadata.repository_url,
            metadata={
                "default_branch": metadata.default_branch,
                "latest_commit": metadata.latest_commit,
                "local_path": metadata.local_path,
            },
            technology_stack=tech_stack,
            project_structure_summary=summary,
            number_of_files=metadata.total_files,
            number_of_apis_discovered=len(api_inventory),
            api_inventory=api_inventory,
        )

    def save_json_report(self, report: RepositoryAnalysisReport) -> Path:
        settings.reports_path.mkdir(parents=True, exist_ok=True)
        output_path = settings.reports_path / f"{report.analysis_id}.json"
        output_path.write_text(
            json.dumps(report.model_dump(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return output_path
