"""
RepositoryHealthScoreAgent — computes overall 0-100 repo score across 8 categories.

Reuses pre-computed outputs from Bug Detection, Pattern Detection, Architecture Drift,
Code Insights, and Tech Stack to produce a radar chart breakdown and recommendations.
"""
from __future__ import annotations

import logging
from typing import Any

from app.schemas.v2_schemas import (
    HealthCategoryScore,
    RepositoryHealthReport,
)

logger = logging.getLogger(__name__)


class RepositoryHealthScoreAgent:
    """Calculates overall repository health score and 8-category quality breakdown."""

    def calculate_health(
        self,
        report_data: dict[str, Any],
        drift_report: dict[str, Any] | None = None,
    ) -> RepositoryHealthReport:
        code_insights = report_data.get("code_insights") or {}
        issues = code_insights.get("issues") or []
        notable_patterns = code_insights.get("notable_patterns") or []
        readme_summary = report_data.get("readme_summary")
        tech_stack = report_data.get("technology_stack") or {}
        dep_graph = report_data.get("dependency_graph") or {}

        # ── 1. Category 1: Architecture (0-100) ───────────────────────────────
        arch_score = 95.0
        if drift_report:
            crit = drift_report.get("critical_count", 0)
            warn = drift_report.get("warning_count", 0)
            arch_score -= (crit * 20.0 + warn * 8.0)
        cycles = len(dep_graph.get("cycles", [])) if isinstance(dep_graph, dict) else 0
        arch_score -= (cycles * 15.0)
        arch_score = max(10.0, min(100.0, round(arch_score, 1)))

        # ── 2. Category 2: Security (0-100) ───────────────────────────────────
        sec_score = 90.0
        high_issues = sum(1 for i in issues if i.get("severity") == "high")
        hardcoded = sum(1 for p in notable_patterns if "hardcoded" in str(p).lower())
        raw_sql = sum(1 for p in notable_patterns if "raw sql" in str(p).lower())

        sec_score -= (high_issues * 15.0 + hardcoded * 25.0 + raw_sql * 10.0)
        sec_score = max(10.0, min(100.0, round(sec_score, 1)))

        # ── 3. Category 3: Maintainability (0-100) ─────────────────────────────
        maint_score = 88.0
        skipped = code_insights.get("skipped_files_count", 0)
        maint_score -= min(30.0, skipped * 2.0)
        maint_score = max(20.0, min(100.0, round(maint_score, 1)))

        # ── 4. Category 4: Performance (0-100) ────────────────────────────────
        perf_score = 85.0
        subproc = sum(1 for p in notable_patterns if "subprocess" in str(p).lower())
        perf_score -= (subproc * 10.0)
        perf_score = max(30.0, min(100.0, round(perf_score, 1)))

        # ── 5. Category 5: Documentation (0-100) ──────────────────────────────
        doc_score = 90.0 if readme_summary else 40.0

        # ── 6. Category 6: Testing (0-100) ───────────────────────────────────
        frameworks = tech_stack.get("frameworks", [])
        languages = tech_stack.get("languages", [])
        has_test_framework = any("test" in f.lower() or "pytest" in f.lower() or "jest" in f.lower() for f in frameworks)
        test_score = 85.0 if has_test_framework else 60.0

        # ── 7. Category 7: Complexity (0-100) ─────────────────────────────────
        total_files = report_data.get("number_of_files", 10)
        comp_score = 90.0 - min(40.0, total_files * 0.5)
        comp_score = max(30.0, min(100.0, round(comp_score, 1)))

        # ── 8. Category 8: Technical Debt (0-100) ─────────────────────────────
        debt_comments = sum(1 for p in notable_patterns if any(k in str(p).lower() for k in ("todo", "fixme", "hack")))
        debt_score = 95.0 - (debt_comments * 5.0 + len(issues) * 4.0)
        debt_score = max(10.0, min(100.0, round(debt_score, 1)))

        category_scores = [
            HealthCategoryScore(category="Architecture", score=arch_score, details="Evaluates DAG structure, layer isolation, and circular dependencies."),
            HealthCategoryScore(category="Security", score=sec_score, details="Evaluates static bugs, hardcoded secrets, and raw SQL risks."),
            HealthCategoryScore(category="Maintainability", score=maint_score, details="Evaluates module layout and file prioritization coverage."),
            HealthCategoryScore(category="Performance", score=perf_score, details="Evaluates synchronous execution patterns and external calls."),
            HealthCategoryScore(category="Documentation", score=doc_score, details="Evaluates README presence and API documentation coverage."),
            HealthCategoryScore(category="Testing", score=test_score, details="Evaluates test suite setup and testing framework presence."),
            HealthCategoryScore(category="Complexity", score=comp_score, details="Evaluates repository file volume and AST structural depth."),
            HealthCategoryScore(category="Technical Debt", score=debt_score, details="Evaluates TODO/FIXME comments and code smell counts."),
        ]

        # Calculate Overall Score (weighted average)
        overall = (
            arch_score * 0.20 +
            sec_score * 0.20 +
            maint_score * 0.15 +
            debt_score * 0.15 +
            doc_score * 0.10 +
            perf_score * 0.10 +
            test_score * 0.05 +
            comp_score * 0.05
        )
        overall_score = round(overall, 1)

        # Strengths & Weaknesses
        strengths: list[str] = []
        weaknesses: list[str] = []
        recommendations: list[str] = []

        if readme_summary:
            strengths.append("Comprehensive README documentation present.")
        else:
            weaknesses.append("Missing README file in repository root.")
            recommendations.append("Add a README.md explaining project setup, requirements, and usage.")

        if sec_score >= 80.0:
            strengths.append("Strong security posture — zero hardcoded credentials detected.")
        else:
            weaknesses.append("Security risks or hardcoded secrets detected in codebase.")
            recommendations.append("Audit codebase for exposed API keys and migrate to environment variables.")

        if arch_score >= 85.0:
            strengths.append("Clean architectural layout with zero circular module dependencies.")
        else:
            weaknesses.append("Architectural drift or direct database access from API route handlers detected.")
            recommendations.append("Decouple route controllers from DB sessions by introducing a Service layer.")

        if len(issues) == 0:
            strengths.append("Clean static scan — zero linter bugs or code smells detected.")
        else:
            weaknesses.append(f"{len(issues)} code quality / bug issue(s) detected during analysis.")
            recommendations.append("Review the Bug Report tab and resolve high-severity static smells.")

        return RepositoryHealthReport(
            overall_score=overall_score,
            category_scores=category_scores,
            strengths=strengths[:4],
            weaknesses=weaknesses[:4],
            actionable_recommendations=recommendations[:5],
        )
