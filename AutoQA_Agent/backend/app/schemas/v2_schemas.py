"""
V2.0 Schemas for AutoQA Agent enterprise expansion.

Defines Pydantic models for:
1. ChangeImpactAnalysisAgent
2. ArchitectureDriftAgent
3. CrossRepoDuplicateAgent
4. AIProjectOnboardingAgent
5. RepositoryHealthScoreAgent
6. TechnicalDebtPrioritizationAgent
"""
from typing import Any, Optional
from pydantic import BaseModel, Field


# ── 1. Change Impact Analysis ─────────────────────────────────────────────────

class ImpactedFile(BaseModel):
    file_path: str
    distance: int                 # 1-hop, 2-hop, 3-hop
    impact_type: str              # "direct_dependent" | "transitive_dependent" | "shared_import"
    risk_score: float             # 0.0 - 1.0


class ChangeImpactResult(BaseModel):
    target_file: str
    impact_score: float           # 0 - 100
    risk_level: str               # "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"
    impacted_files: list[ImpactedFile] = []
    impacted_routes: list[str] = []
    impacted_services: list[str] = []
    impacted_modules: list[str] = []
    impacted_models: list[str] = []
    explanation: str


# ── 2. Architecture Drift Audit ───────────────────────────────────────────────

class ArchitectureViolation(BaseModel):
    rule_id: str                  # e.g. "ROUTE_DIRECT_DB", "CIRCULAR_DEPENDENCY", "LAYER_INVERSION"
    title: str
    severity: str                 # "CRITICAL" | "WARNING" | "SUGGESTION"
    violating_files: list[str] = []
    reason: str
    expected_architecture: str
    suggested_fix: str


class ArchitectureDriftReport(BaseModel):
    total_violations: int = 0
    critical_count: int = 0
    warning_count: int = 0
    suggestion_count: int = 0
    violations: list[ArchitectureViolation] = []
    summary: str


# ── 3. Cross-Repo Duplication ──────────────────────────────────────────────────

class DuplicateFilePair(BaseModel):
    file_a: str
    file_b: str
    similarity_percentage: float   # 0 - 100


class DuplicateFunctionPair(BaseModel):
    function_a: str
    function_b: str
    file_a: str
    file_b: str
    similarity_percentage: float


class CrossRepoComparisonRequest(BaseModel):
    analysis_id_a: str
    analysis_id_b: str


class CrossRepoComparisonResult(BaseModel):
    repo_a_name: str
    repo_b_name: str
    overall_similarity_percentage: float
    duplicated_files: list[DuplicateFilePair] = []
    duplicated_functions: list[DuplicateFunctionPair] = []
    comparison_summary: str
    # V3 Enhanced fields
    architecture_similarity: float = 0.0
    api_similarity: float = 0.0
    feature_similarity: float = 0.0
    module_similarity: float = 0.0
    code_similarity: float = 0.0
    duplicate_file_count: int = 0
    duplicate_function_count: int = 0
    relationship_type: str = "Independent Repository"
    relationship_confidence: float = 0.0
    relationship_reasoning: str = ""
    clone_detected: bool = False
    clone_threshold: float = 98.0
    clone_banner_message: Optional[str] = None


# ── 4. AI Project Onboarding ──────────────────────────────────────────────────

class ReadingPathItem(BaseModel):
    step: int
    file_path: str
    title: str
    importance: str               # "CRITICAL" | "CORE" | "UTILITY"
    reason: str


class OnboardingQuizOption(BaseModel):
    text: str
    is_correct: bool


class OnboardingQuiz(BaseModel):
    question: str
    options: list[OnboardingQuizOption]
    explanation: str
    citation_file: str
    citation_line: Optional[int] = None


class ProjectOnboardingReport(BaseModel):
    recommended_reading_path: list[ReadingPathItem] = []
    auth_flow_summary: Optional[str] = None
    database_layer_summary: Optional[str] = None
    core_apis_summary: Optional[str] = None
    business_logic_summary: Optional[str] = None
    quizzes: list[OnboardingQuiz] = []


# ── 5. Repository Health Score ────────────────────────────────────────────────

class HealthCategoryScore(BaseModel):
    category: str                 # "Architecture", "Security", "Maintainability", etc.
    score: float                  # 0 - 100
    details: str


class RepositoryHealthReport(BaseModel):
    overall_score: float          # 0 - 100
    category_scores: list[HealthCategoryScore] = []
    strengths: list[str] = []
    weaknesses: list[str] = []
    actionable_recommendations: list[str] = []


# ── 6. Technical Debt Prioritization ──────────────────────────────────────────

class TechnicalDebtItem(BaseModel):
    rank: int
    title: str
    category: str                 # "Security" | "Bug" | "Architecture Drift" | "Code Smell" | "Tech Debt"
    severity: str                 # "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"
    file_path: str
    line_number: Optional[int] = None
    priority_score: float         # Higher score = fix first
    estimated_fix_time: str       # e.g. "15 mins", "1 hour", "1 day"
    why_fix_first: str
    suggested_fix: str


class TechnicalDebtReport(BaseModel):
    total_debt_items: int = 0
    estimated_total_fix_hours: float = 0.0
    items: list[TechnicalDebtItem] = []


# ── 7. Execution Flow (V3) ────────────────────────────────────────────────────

class ExecutionFlowNode(BaseModel):
    id: str                        # unique node ID e.g. "AuthService.login"
    label: str                     # display label
    node_type: str                 # "api_endpoint" | "function" | "class" | "db_call" | "external_http" | "module"
    file_path: str
    line_number: Optional[int] = None
    confidence: float = 1.0        # 0.0 - 1.0
    metadata: dict = {}


class ExecutionFlowEdge(BaseModel):
    from_id: str
    to_id: str
    edge_type: str                 # "calls" | "returns" | "raises" | "db_query" | "http_request"
    label: Optional[str] = None


class ExecutionFlowResult(BaseModel):
    entry_point: str               # starting node label (API path or function name)
    nodes: list[ExecutionFlowNode] = []
    edges: list[ExecutionFlowEdge] = []
    execution_depth: int = 0
    db_operations_count: int = 0
    external_http_calls_count: int = 0
    exceptions_handled: list[str] = []
    confidence_score: float = 0.0  # 0.0 - 1.0 for overall graph confidence
    summary: str = ""


# ── 8. Feature Extraction & Functional Map (V3) ───────────────────────────────

class DetectedBusinessFeature(BaseModel):
    feature_name: str
    description: str
    confidence_score: float        # 0.0 - 1.0
    related_apis: list[str] = []
    related_controllers: list[str] = []
    related_services: list[str] = []
    related_models: list[str] = []
    related_db_tables: list[str] = []
    related_config_files: list[str] = []
    related_env_vars: list[str] = []
    dependencies: list[str] = []
    implementation_files: list[str] = []


class FeatureMapResult(BaseModel):
    total_features_detected: int = 0
    features: list[DetectedBusinessFeature] = []
    summary: str = ""
