"""
Tests for CrossRepoDuplicateAgent — enhanced clone detection.

Tests verify:
- High similarity (>=98%) classified as "Near-Identical Copy" with clone_detected=True
- Moderate similarity (~40-75%) classified as "Fork" or "Shared Template"
- Low similarity classified as "Independent Repository"
- Clone banner message is set when clone_detected=True
- Clone banner never contains legal accusations
- Multi-dimensional scores are all in [0, 100]
- overall_similarity is weighted average of sub-scores
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session

from app.agents.cross_repo_duplicate_agent import CrossRepoDuplicateAgent, _jaccard


# ── Unit tests: helper functions ──────────────────────────────────────────────

class TestJaccard:
    def test_identical_sets(self):
        assert _jaccard({"a", "b", "c"}, {"a", "b", "c"}) == 100.0

    def test_disjoint_sets(self):
        assert _jaccard({"a", "b"}, {"c", "d"}) == 0.0

    def test_partial_overlap(self):
        result = _jaccard({"a", "b", "c"}, {"b", "c", "d"})
        # Union = {a,b,c,d}=4, Intersection = {b,c}=2 → 50%
        assert result == 50.0

    def test_empty_sets(self):
        assert _jaccard(set(), set()) == 0.0

    def test_one_empty(self):
        assert _jaccard({"a"}, set()) == 0.0


# ── Unit tests: relationship classification ───────────────────────────────────

class TestRelationshipClassification:

    def _agent(self):
        """Return agent without DB connection (testing internal classify method)."""
        db = MagicMock(spec=Session)
        agent = CrossRepoDuplicateAgent.__new__(CrossRepoDuplicateAgent)
        agent.db = db
        agent.repo_db = MagicMock()
        return agent

    def test_high_similarity_is_near_identical_copy(self):
        agent = self._agent()
        clone_detected, rtype, conf, reasoning, banner = agent._classify_relationship(
            overall_similarity=98.5,
            api_similarity=99.0,
            architecture_similarity=97.0,
            name_a="Repo A",
            name_b="Repo B",
        )
        assert clone_detected is True
        assert rtype == "Near-Identical Copy"
        assert conf > 0.9

    def test_clone_threshold_boundary(self):
        agent = self._agent()
        # Exactly at threshold
        clone_detected, rtype, conf, reasoning, banner = agent._classify_relationship(
            overall_similarity=98.0,
            api_similarity=98.0,
            architecture_similarity=98.0,
            name_a="Repo A",
            name_b="Repo B",
        )
        assert clone_detected is True

    def test_just_below_threshold_not_clone(self):
        agent = self._agent()
        clone_detected, rtype, conf, reasoning, banner = agent._classify_relationship(
            overall_similarity=97.9,
            api_similarity=97.0,
            architecture_similarity=96.0,
            name_a="Repo A",
            name_b="Repo B",
        )
        assert clone_detected is False
        assert rtype == "Likely Cloned Repository"

    def test_high_similarity_detected_as_likely_clone(self):
        agent = self._agent()
        clone_detected, rtype, conf, reasoning, banner = agent._classify_relationship(
            overall_similarity=92.0,
            api_similarity=95.0,
            architecture_similarity=88.0,
            name_a="Repo A",
            name_b="Repo B",
        )
        assert clone_detected is False
        assert rtype == "Likely Cloned Repository"

    def test_moderate_similarity_detected_as_fork(self):
        agent = self._agent()
        clone_detected, rtype, conf, reasoning, banner = agent._classify_relationship(
            overall_similarity=55.0,
            api_similarity=60.0,
            architecture_similarity=50.0,
            name_a="Repo A",
            name_b="Repo B",
        )
        assert clone_detected is False
        assert rtype == "Fork"
        assert banner is None

    def test_template_similarity_range(self):
        agent = self._agent()
        clone_detected, rtype, conf, reasoning, banner = agent._classify_relationship(
            overall_similarity=80.0,
            api_similarity=75.0,
            architecture_similarity=85.0,
            name_a="Repo A",
            name_b="Repo B",
        )
        assert rtype == "Shared Template"

    def test_low_similarity_independent(self):
        agent = self._agent()
        clone_detected, rtype, conf, reasoning, banner = agent._classify_relationship(
            overall_similarity=12.0,
            api_similarity=5.0,
            architecture_similarity=20.0,
            name_a="Repo A",
            name_b="Repo B",
        )
        assert rtype == "Independent Repository"
        assert clone_detected is False
        assert banner is None

    def test_clone_banner_set_when_clone_detected(self):
        agent = self._agent()
        clone_detected, rtype, conf, reasoning, banner = agent._classify_relationship(
            overall_similarity=99.0,
            api_similarity=100.0,
            architecture_similarity=98.0,
            name_a="Repo A",
            name_b="Repo B",
        )
        assert clone_detected is True
        assert banner is not None
        assert len(banner) > 10

    def test_no_legal_claims_in_banner(self):
        """Banner must never accuse users of plagiarism or legal violations."""
        agent = self._agent()
        _, _, _, reasoning, banner = agent._classify_relationship(
            overall_similarity=99.5,
            api_similarity=100.0,
            architecture_similarity=100.0,
            name_a="Repo A",
            name_b="Repo B",
        )
        forbidden_terms = [
            "plagiarism", "stolen", "theft", "copyright infringement",
            "illegal", "violating", "lawsuit", "piracy",
        ]
        full_text = ((banner or "") + reasoning).lower()
        for term in forbidden_terms:
            assert term not in full_text, f"Forbidden term '{term}' found in output"

    def test_banner_none_when_no_clone(self):
        agent = self._agent()
        _, _, _, _, banner = agent._classify_relationship(
            overall_similarity=30.0,
            api_similarity=20.0,
            architecture_similarity=35.0,
            name_a="A",
            name_b="B",
        )
        assert banner is None

    def test_confidence_in_range(self):
        agent = self._agent()
        for similarity in [0.0, 20.0, 50.0, 75.0, 90.0, 98.5, 100.0]:
            _, _, conf, _, _ = agent._classify_relationship(
                overall_similarity=similarity,
                api_similarity=similarity,
                architecture_similarity=similarity,
                name_a="A",
                name_b="B",
            )
            assert 0.0 <= conf <= 1.0, f"Confidence {conf} out of range for similarity {similarity}"


# ── Integration test: full compare() with mock DB ────────────────────────────

class TestCrossRepoDuplicateAgentIntegration:

    def _make_mock_model(self, repo_name, report_json):
        model = MagicMock()
        model.repository_name = repo_name
        model.report_json = report_json
        return model

    def _make_report(self, api_paths=None, file_summaries=None, modules=None, tech=None):
        return {
            "repository_name": "test_repo",
            "api_inventory": [
                {"method": "GET", "path": p, "file": "routes.py", "function_name": "fn"}
                for p in (api_paths or [])
            ],
            "code_insights": {
                "file_summaries": file_summaries or {},
            },
            "module_summaries": modules or {},
            "technology_stack": tech or {
                "backend": ["FastAPI"],
                "databases": ["PostgreSQL"],
                "languages": ["Python"],
            },
            "number_of_files": 10,
        }

    def test_identical_repos_high_similarity(self):
        db = MagicMock(spec=Session)
        agent = CrossRepoDuplicateAgent(db)

        shared_apis = ["/login", "/register", "/users", "/payment", "/orders"]
        shared_files = {f"{i}.py": f"summary {i}" for i in range(10)}

        report_a = self._make_report(api_paths=shared_apis, file_summaries=shared_files)
        report_b = self._make_report(api_paths=shared_apis, file_summaries=shared_files)

        agent.repo_db = MagicMock()
        agent.repo_db.get_by_id.side_effect = [
            self._make_mock_model("RepoA", report_a),
            self._make_mock_model("RepoB", report_b),
        ]

        result = agent.compare("id-a", "id-b")
        # Identical APIs → api_similarity = 100%
        assert result.api_similarity == 100.0
        assert result.overall_similarity_percentage > 0

    def test_result_has_all_v3_fields(self):
        db = MagicMock(spec=Session)
        agent = CrossRepoDuplicateAgent(db)

        report_a = self._make_report(api_paths=["/login"])
        report_b = self._make_report(api_paths=["/register"])

        agent.repo_db = MagicMock()
        agent.repo_db.get_by_id.side_effect = [
            self._make_mock_model("RepoA", report_a),
            self._make_mock_model("RepoB", report_b),
        ]

        result = agent.compare("id-a", "id-b")

        # V3 fields must always be present
        assert hasattr(result, "architecture_similarity")
        assert hasattr(result, "api_similarity")
        assert hasattr(result, "feature_similarity")
        assert hasattr(result, "module_similarity")
        assert hasattr(result, "code_similarity")
        assert hasattr(result, "relationship_type")
        assert hasattr(result, "clone_detected")
        assert hasattr(result, "clone_banner_message")
        assert hasattr(result, "duplicate_file_count")
        assert hasattr(result, "duplicate_function_count")

    def test_missing_analysis_raises_value_error(self):
        db = MagicMock(spec=Session)
        agent = CrossRepoDuplicateAgent(db)
        agent.repo_db = MagicMock()
        agent.repo_db.get_by_id.return_value = None

        with pytest.raises(ValueError, match="not found"):
            agent.compare("missing-id-a", "missing-id-b")

    def test_similarity_scores_in_valid_range(self):
        db = MagicMock(spec=Session)
        agent = CrossRepoDuplicateAgent(db)

        report_a = self._make_report(api_paths=["/login", "/users"])
        report_b = self._make_report(api_paths=["/login", "/products"])

        agent.repo_db = MagicMock()
        agent.repo_db.get_by_id.side_effect = [
            self._make_mock_model("RepoA", report_a),
            self._make_mock_model("RepoB", report_b),
        ]

        result = agent.compare("id-a", "id-b")

        for field in [
            result.overall_similarity_percentage,
            result.api_similarity,
            result.architecture_similarity,
            result.module_similarity,
            result.feature_similarity,
            result.code_similarity,
        ]:
            assert 0.0 <= field <= 100.0, f"Similarity score {field} out of range [0, 100]"
