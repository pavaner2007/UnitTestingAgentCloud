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
