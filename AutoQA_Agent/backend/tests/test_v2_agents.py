"""
Unit tests for AutoQA Agent V2.0 Enterprise Agents:
- ChangeImpactAnalysisAgent
- ArchitectureDriftAgent
- CrossRepoDuplicateAgent
- AIProjectOnboardingAgent
- RepositoryHealthScoreAgent
- TechnicalDebtPrioritizationAgent
"""
import pytest
from unittest.mock import MagicMock

from app.agents.change_impact_agent import ChangeImpactAnalysisAgent
from app.agents.architecture_drift_agent import ArchitectureDriftAgent
from app.agents.cross_repo_duplicate_agent import CrossRepoDuplicateAgent
from app.agents.project_onboarding_agent import AIProjectOnboardingAgent
from app.agents.repository_health_agent import RepositoryHealthScoreAgent
from app.agents.technical_debt_agent import TechnicalDebtPrioritizationAgent


# ── 1. ChangeImpactAnalysisAgent Tests ────────────────────────────────────────

def test_change_impact_agent_basic():
    agent = ChangeImpactAnalysisAgent()
    dep_graph = {
        "nodes": [{"file": "app/routes.py"}, {"file": "app/services.py"}],
        "edges": [{"from": "app/routes.py", "to": "app/services.py"}],
    }
    api_inventory = [{"method": "GET", "path": "/users", "file": "app/routes.py"}]

    res = agent.analyze_impact("app/services.py", dep_graph, api_inventory)
    assert res.target_file == "app/services.py"
    assert res.impact_score > 0
    assert len(res.impacted_files) == 1
    assert res.impacted_files[0].file_path == "app/routes.py"
    assert len(res.impacted_routes) == 1
    assert "GET /users" in res.impacted_routes[0]


# ── 2. ArchitectureDriftAgent Tests ──────────────────────────────────────────

def test_architecture_drift_agent_detects_violations():
    agent = ArchitectureDriftAgent()
    dep_graph = {
        "nodes": [{"file": "app/routes.py"}, {"file": "app/db.py"}],
        "edges": [{"from": "app/routes.py", "to": "app/db.py"}],
        "cycles": [["app/a.py", "app/b.py", "app/a.py"]],
    }
    api_inv = [{"file": "app/routes.py"}]

    res = agent.audit(dep_graph, api_inv, analyzed_files=["app/routes.py", "app/db.py"])
    assert res.total_violations >= 2
    rule_ids = [v.rule_id for v in res.violations]
    assert "CIRCULAR_DEPENDENCY" in rule_ids
    assert "ROUTE_DIRECT_DB" in rule_ids


# ── 3. CrossRepoDuplicateAgent Tests ─────────────────────────────────────────

def test_cross_repo_duplicate_agent_compare():
    mock_db = MagicMock()
    agent = CrossRepoDuplicateAgent(mock_db)

    # Mock AnalysisRepository save/get
    mock_model_a = MagicMock()
    mock_model_a.repository_name = "Repo A"
    mock_model_a.report_json = {
        "repository_name": "Repo A",
        "api_inventory": [{"method": "GET", "path": "/api/v1/users", "function_name": "get_users", "file": "users.py"}],
        "code_insights": {"file_summaries": {"users.py": "Users module"}},
    }

    mock_model_b = MagicMock()
    mock_model_b.repository_name = "Repo B"
    mock_model_b.report_json = {
        "repository_name": "Repo B",
        "api_inventory": [{"method": "GET", "path": "/api/v1/users", "function_name": "get_users", "file": "users.py"}],
        "code_insights": {"file_summaries": {"users.py": "Users module"}},
    }

    agent.repo_db.get_by_id = lambda aid: mock_model_a if aid == "id-a" else mock_model_b

    res = agent.compare("id-a", "id-b")
    assert res.repo_a_name == "Repo A"
    assert res.repo_b_name == "Repo B"
    assert res.overall_similarity_percentage > 0
    assert len(res.duplicated_functions) == 1


# ── 4. AIProjectOnboardingAgent Tests ─────────────────────────────────────────

def test_project_onboarding_agent_generate():
    agent = AIProjectOnboardingAgent()
    report_data = {
        "repository_name": "TestRepo",
        "technology_stack": {"backend": ["FastAPI"], "databases": ["PostgreSQL"]},
        "api_inventory": [{"method": "POST", "path": "/login", "file": "app/auth.py", "line_number": 15}],
        "readme_summary": "Test repo summary.",
        "code_insights": {"file_summaries": {"app/auth.py": "Auth code"}},
    }

    res = agent.generate_onboarding(report_data)
    assert len(res.recommended_reading_path) > 0
    assert res.recommended_reading_path[0].file_path == "README.md"
    assert len(res.quizzes) >= 2
    assert "FastAPI" in res.quizzes[0].options[0].text


# ── 5. RepositoryHealthScoreAgent Tests ───────────────────────────────────────

def test_repository_health_agent_score():
    agent = RepositoryHealthScoreAgent()
    report_data = {
        "number_of_files": 12,
        "readme_summary": "Has README",
        "technology_stack": {"frameworks": ["pytest"]},
        "code_insights": {"issues": [], "notable_patterns": []},
    }

    res = agent.calculate_health(report_data)
    assert 0 <= res.overall_score <= 100
    assert len(res.category_scores) == 8
    assert len(res.strengths) > 0


# ── 6. TechnicalDebtPrioritizationAgent Tests ────────────────────────────────

def test_technical_debt_agent_prioritize():
    agent = TechnicalDebtPrioritizationAgent()
    report_data = {
        "code_insights": {
            "issues": [
                {"severity": "high", "rule": "E722", "message": "bare except", "file": "app/main.py", "line": 42}
            ],
            "notable_patterns": ["Hardcoded secret in app/config.py"],
        }
    }
    drift_data = {
        "violations": [
            {"severity": "CRITICAL", "rule_id": "ROUTE_DIRECT_DB", "title": "Route direct DB", "violating_files": ["app/routes.py"]}
        ]
    }

    res = agent.prioritize_debt(report_data, drift_data)
    assert res.total_debt_items == 3
    assert res.items[0].rank == 1
    assert res.items[0].priority_score >= res.items[1].priority_score
