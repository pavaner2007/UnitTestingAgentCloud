from typing import Any, Optional
from pydantic import BaseModel, Field, HttpUrl


class AnalyzeRepositoryRequest(BaseModel):
    github_url: HttpUrl = Field(..., description="Public GitHub repository URL")


class ApiEndpoint(BaseModel):
    method: str
    path: str
    framework: str
    file: str
    line_number: int | None = None
    function_name: str | None = None


class TechStackResponse(BaseModel):
    frontend: list[str] = []
    backend: list[str] = []
    languages: list[str] = []
    databases: list[str] = []
    frameworks: list[str] = []
    package_managers: list[str] = []
    raw_evidence: dict[str, list[str]] = {}


class ProjectStructureSummary(BaseModel):
    directories: int
    files: int
    top_level_items: list[str]
    important_files: list[str]


class DetectedFeature(BaseModel):
    """A feature detected from code evidence (never inferred from repo name)."""
    name: str
    evidence: list[str] = []  # e.g. ["POST /login", "auth middleware", "routes/auth.js"]


class CodeIssue(BaseModel):
    """
    A single detected bug, smell, or quality issue.
    GROQ BOUNDARY: The full `issues` list must NEVER be forwarded to Groq.
    Only `issues_summary` (count dict) may be included in the Groq facts payload.
    """
    file: str
    line: Optional[int] = None
    severity: str           # "high" | "medium" | "low"
    source: str             # "linter" | "static_smell"
    rule: str               # e.g. "ruff:E722", "bare_except", "hardcoded_secret"
    message: str
    suggestion: str = ""    # Human-readable fix recommendation


class DependencyGraphNode(BaseModel):
    file: str
    dependency_count: int = 0  # In-degree (how many files depend on this file)


class DependencyGraphEdge(BaseModel):
    from_file: str = Field(..., alias="from")
    to_file: str = Field(..., alias="to")

    model_config = {"populate_by_name": True}


class DependencyGraph(BaseModel):
    nodes: list[DependencyGraphNode] = []
    edges: list[DependencyGraphEdge] = []
    cycles: list[list[str]] = []
    most_depended_on: Optional[str] = None


class CodeInsights(BaseModel):
    """
    Output of the hierarchical code analysis stage.

    GROQ BOUNDARY: Only `module_summaries`, `notable_patterns`, and
    `issues_summary` (count dict only) are forwarded to Groq.
    `file_summaries`, `issues` (full list), and raw chunk content
    must NEVER be sent to Groq.
    This boundary is enforced in analysis_service.py and covered by
    test_groq_boundary.py.
    """
    analyzed_files: list[str] = []
    skipped_files_count: int = 0
    skipped_files_breakdown: dict[str, int] = {}
    # e.g. {"excluded_vendor": 20, "excluded_token_budget": 5, "excluded_binary": 3}
    # file_summaries maps rel_path → one-sentence summary. NOT forwarded to Groq.
    file_summaries: dict[str, str] = {}
    # module_summaries maps directory → summary. Forwarded to Groq as structured facts.
    module_summaries: dict[str, str] = {}
    # Deterministic regex-detected patterns. Forwarded to Groq as structured facts.
    notable_patterns: list[str] = []
    cache_hit_rate: float = 0.0
    # Bug / code-quality issues. Full list for UI only — NOT forwarded to Groq.
    issues: list[CodeIssue] = []
    # Count-only summary — safe to forward to Groq.
    issues_summary: dict[str, int] = {}  # {"high": N, "medium": N, "low": N}
    # File import graph
    dependency_graph: Optional[DependencyGraph] = None


class RepositoryAnalysisReport(BaseModel):
    analysis_id: str
    repository_name: str
    repository_url: str
    metadata: dict[str, Any]
    technology_stack: TechStackResponse
    project_structure_summary: ProjectStructureSummary
    number_of_files: int
    number_of_apis_discovered: int
    api_inventory: list[ApiEndpoint]

    # Ollama-generated summaries
    readme_summary: str | None = None
    module_summaries: dict[str, str] = {}  # module_name → summary

    # Groq-generated analysis (from structured facts only)
    ai_explanation: dict[str, Any] | None = None
    detected_features: list[DetectedFeature] = []
    architecture_notes: str | None = None
    workflow: list[str] = []
    confidence_score: float | None = None  # 0–100

    # New hierarchical code analysis (optional — backward compatible)
    # When null: old reports deserialize fine; frontend hides the Code Insights panel.
    code_insights: CodeInsights | None = None
    dependency_graph: DependencyGraph | None = None

    # V2.0 Enterprise Analysis Extensions (optional — backward compatible)
    architecture_drift: Optional[Any] = None
    project_onboarding: Optional[Any] = None
    repository_health: Optional[Any] = None
    technical_debt: Optional[Any] = None


class AnalyzeRepositoryResponse(BaseModel):
    analysis_id: str
    status: str        # "processing" | "completed"
    cached: bool = False
    report: RepositoryAnalysisReport | None = None


class HealthResponse(BaseModel):
    status: str
    service: str
