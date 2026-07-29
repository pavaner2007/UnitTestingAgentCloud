"""
Tests for FeatureExtractionAgent.

Tests verify:
- Authentication feature detected from /auth/* routes
- Payment feature detected from /payment/* routes
- No duplicate features in output
- Confidence scores always in [0.0, 1.0]
- Empty API inventory returns valid FeatureMapResult with 0 features
- Environment variable matching
"""
from __future__ import annotations

import pytest
from pathlib import Path

from app.agents.feature_extraction_agent import (
    FeatureExtractionAgent,
    _match_domain,
    _file_hints_match,
    _env_var_match,
    _parse_env_file,
)
from app.schemas.v2_schemas import FeatureMapResult, DetectedBusinessFeature


# ── Unit tests: domain matching functions ─────────────────────────────────────

class TestMatchDomain:
    def test_auth_routes(self):
        assert _match_domain("/auth/login") == "Authentication"
        assert _match_domain("/login") == "Authentication"
        assert _match_domain("/register") == "Authentication"
        assert _match_domain("/token/refresh") == "Authentication"
        assert _match_domain("/logout") == "Authentication"

    def test_payment_routes(self):
        assert _match_domain("/payment/checkout") == "Payment & Billing"
        assert _match_domain("/stripe/webhook") == "Payment & Billing"
        assert _match_domain("/order/create") == "Payment & Billing"
        assert _match_domain("/billing/subscription") == "Payment & Billing"

    def test_user_routes(self):
        assert _match_domain("/users") == "User Management"
        assert _match_domain("/user/profile") == "User Management"
        assert _match_domain("/account/settings") == "User Management"

    def test_search_routes(self):
        assert _match_domain("/search") == "Search"
        assert _match_domain("/search/autocomplete") == "Search"

    def test_upload_routes(self):
        assert _match_domain("/upload") == "File Upload & Storage"
        assert _match_domain("/file/download") == "File Upload & Storage"

    def test_unknown_route_returns_none(self):
        assert _match_domain("/xyz/unknown/path") is None

    def test_ai_routes(self):
        assert _match_domain("/ai/predict") == "AI / Machine Learning"
        assert _match_domain("/chatbot/message") == "AI / Machine Learning"

    def test_admin_routes(self):
        assert _match_domain("/admin") == "Admin Dashboard"
        assert _match_domain("/admin/dashboard") == "Admin Dashboard"

    def test_analytics_routes(self):
        assert _match_domain("/analytics/events") == "Analytics & Reporting"
        assert _match_domain("/report/summary") == "Analytics & Reporting"


class TestFileHintsMatch:
    def test_auth_file(self):
        assert _file_hints_match("app/auth_service.py", ["auth", "login"]) is True

    def test_user_file(self):
        assert _file_hints_match("models/user_model.py", ["user", "profile"]) is True

    def test_unrelated_file(self):
        assert _file_hints_match("utils/helpers.py", ["payment", "billing"]) is False


class TestEnvVarMatch:
    def test_jwt_env_vars(self):
        env_vars = ["JWT_SECRET", "JWT_EXPIRY", "DATABASE_URL"]
        matched = _env_var_match(env_vars, ["JWT_SECRET", "JWT_EXPIRY"])
        assert "JWT_SECRET" in matched
        assert "JWT_EXPIRY" in matched
        assert "DATABASE_URL" not in matched

    def test_stripe_env_vars(self):
        env_vars = ["STRIPE_KEY", "STRIPE_SECRET", "EMAIL_HOST"]
        matched = _env_var_match(env_vars, ["STRIPE_KEY", "STRIPE_SECRET"])
        assert "STRIPE_KEY" in matched
        assert "STRIPE_SECRET" in matched
        assert "EMAIL_HOST" not in matched

    def test_empty_env_vars(self):
        assert _env_var_match([], ["JWT_SECRET"]) == []


class TestParseEnvFile:
    def test_parses_valid_env_file(self, tmp_path):
        env_file = tmp_path / ".env.example"
        env_file.write_text("JWT_SECRET=secret\nDATABASE_URL=postgres://localhost\n# comment\n")
        result = _parse_env_file(env_file)
        assert "JWT_SECRET" in result
        assert "DATABASE_URL" in result
        assert "# comment" not in result

    def test_ignores_missing_file(self, tmp_path):
        result = _parse_env_file(tmp_path / ".env.missing")
        assert result == []

    def test_handles_none(self):
        result = _parse_env_file(None)
        assert result == []


# ── Integration tests: FeatureExtractionAgent ─────────────────────────────────

class TestFeatureExtractionAgent:

    def _make_api(self, method, path, file="routes.py", fn=None):
        return {"method": method, "path": path, "file": file, "function_name": fn}

    def test_empty_api_inventory_returns_valid_result(self):
        agent = FeatureExtractionAgent()
        result = agent.extract_features(
            api_inventory=[],
            dep_graph=None,
            code_insights=None,
            tech_stack=None,
            module_summaries=None,
        )
        assert isinstance(result, FeatureMapResult)
        assert result.total_features_detected == 0
        assert result.features == []

    def test_auth_feature_detected(self):
        agent = FeatureExtractionAgent()
        apis = [
            self._make_api("POST", "/login"),
            self._make_api("POST", "/register"),
            self._make_api("POST", "/logout"),
        ]
        result = agent.extract_features(
            api_inventory=apis,
            dep_graph=None,
            code_insights=None,
            tech_stack=None,
            module_summaries=None,
        )
        feature_names = [f.feature_name for f in result.features]
        assert "Authentication" in feature_names, f"Expected Authentication in {feature_names}"

    def test_payment_feature_detected(self):
        agent = FeatureExtractionAgent()
        apis = [
            self._make_api("POST", "/payment/checkout"),
            self._make_api("POST", "/stripe/webhook"),
            self._make_api("GET", "/order/history"),
        ]
        result = agent.extract_features(
            api_inventory=apis,
            dep_graph=None,
            code_insights=None,
            tech_stack=None,
            module_summaries=None,
        )
        feature_names = [f.feature_name for f in result.features]
        assert "Payment & Billing" in feature_names, f"Expected Payment in {feature_names}"

    def test_no_duplicate_features(self):
        """Each feature domain should appear at most once."""
        agent = FeatureExtractionAgent()
        apis = [
            self._make_api("POST", "/login"),
            self._make_api("POST", "/auth/register"),
            self._make_api("GET", "/auth/profile"),
        ]
        result = agent.extract_features(
            api_inventory=apis,
            dep_graph=None,
            code_insights=None,
            tech_stack=None,
            module_summaries=None,
        )
        feature_names = [f.feature_name for f in result.features]
        assert len(feature_names) == len(set(feature_names)), "Duplicate feature domains found"

    def test_confidence_scores_in_range(self):
        agent = FeatureExtractionAgent()
        apis = [
            self._make_api("POST", "/login"),
            self._make_api("GET", "/users"),
            self._make_api("POST", "/payment/charge"),
            self._make_api("GET", "/search"),
        ]
        result = agent.extract_features(
            api_inventory=apis,
            dep_graph=None,
            code_insights=None,
            tech_stack=None,
            module_summaries=None,
        )
        for feature in result.features:
            assert 0.0 <= feature.confidence_score <= 1.0, (
                f"Confidence {feature.confidence_score} out of range for {feature.feature_name}"
            )

    def test_total_features_count_matches_list(self):
        agent = FeatureExtractionAgent()
        apis = [
            self._make_api("POST", "/login"),
            self._make_api("GET", "/users"),
            self._make_api("POST", "/upload"),
        ]
        result = agent.extract_features(
            api_inventory=apis,
            dep_graph=None,
            code_insights=None,
            tech_stack=None,
            module_summaries=None,
        )
        assert result.total_features_detected == len(result.features)

    def test_features_sorted_by_confidence(self):
        agent = FeatureExtractionAgent()
        # Flood auth with many routes to boost its confidence
        apis = [
            self._make_api("POST", "/login"),
            self._make_api("POST", "/register"),
            self._make_api("POST", "/logout"),
            self._make_api("GET", "/auth/me"),
            self._make_api("GET", "/users"),
        ]
        result = agent.extract_features(
            api_inventory=apis,
            dep_graph=None,
            code_insights=None,
            tech_stack=None,
            module_summaries=None,
        )
        if len(result.features) > 1:
            scores = [f.confidence_score for f in result.features]
            assert scores == sorted(scores, reverse=True), "Features not sorted by confidence"

    def test_related_apis_populated(self):
        agent = FeatureExtractionAgent()
        apis = [
            self._make_api("POST", "/login"),
            self._make_api("GET", "/auth/status"),
        ]
        result = agent.extract_features(
            api_inventory=apis,
            dep_graph=None,
            code_insights=None,
            tech_stack=None,
            module_summaries=None,
        )
        auth_feature = next((f for f in result.features if f.feature_name == "Authentication"), None)
        assert auth_feature is not None
        assert len(auth_feature.related_apis) >= 1, "Authentication feature should have related APIs"

    def test_env_var_detection(self, tmp_path):
        """Env vars from .env.example should be matched to features."""
        env_file = tmp_path / ".env.example"
        env_file.write_text("JWT_SECRET=secret\nSTRIPE_KEY=pk_test_xxx\nDATABASE_URL=postgres://\n")

        agent = FeatureExtractionAgent()
        apis = [
            self._make_api("POST", "/login"),
            self._make_api("POST", "/payment/charge"),
        ]
        result = agent.extract_features(
            api_inventory=apis,
            dep_graph=None,
            code_insights=None,
            tech_stack=None,
            module_summaries=None,
            repo_path=tmp_path,
        )
        auth_feature = next((f for f in result.features if f.feature_name == "Authentication"), None)
        if auth_feature:
            assert any("JWT" in ev for ev in auth_feature.related_env_vars), (
                "JWT env vars should be linked to Authentication feature"
            )
