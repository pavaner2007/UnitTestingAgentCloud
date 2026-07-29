"""
AIProjectOnboardingAgent — generates developer onboarding guides, reading paths, and quizzes.

Extracts core architecture, entry points, auth flow, and database models from analysis outputs
to help new developers get up to speed quickly on any codebase.
"""
from __future__ import annotations

import logging
from typing import Any

from app.schemas.v2_schemas import (
    OnboardingQuiz,
    OnboardingQuizOption,
    ProjectOnboardingReport,
    ReadingPathItem,
)

logger = logging.getLogger(__name__)


class AIProjectOnboardingAgent:
    """Generates onboarding guides, recommended reading paths, and interactive codebase quizzes."""

    def generate_onboarding(
        self,
        report_data: dict[str, Any],
    ) -> ProjectOnboardingReport:
        repo_name = report_data.get("repository_name", "Repository")
        tech_stack = report_data.get("technology_stack") or {}
        api_inventory = report_data.get("api_inventory") or []
        code_insights = report_data.get("code_insights") or {}
        file_summaries = code_insights.get("file_summaries") or {}
        module_summaries = report_data.get("module_summaries") or {}
        readme_summary = report_data.get("readme_summary")

        # ── 1. Recommended Reading Path ───────────────────────────────────────
        reading_path: list[ReadingPathItem] = []
        step = 1

        # Priority 1: README / Overview
        if readme_summary:
            reading_path.append(
                ReadingPathItem(
                    step=step,
                    file_path="README.md",
                    title="Project Documentation & Setup",
                    importance="CRITICAL",
                    reason="Provides high-level project vision, setup instructions, and overview.",
                )
            )
            step += 1

        # Priority 2: Config / Main Entry Points
        entry_files = [f for f in file_summaries.keys() if any(k in f.lower() for k in ("main", "app", "index", "server", "config"))]
        for ef in entry_files[:3]:
            reading_path.append(
                ReadingPathItem(
                    step=step,
                    file_path=ef,
                    title=f"Application Entry Point (`{ef.split('/')[-1]}`)",
                    importance="CRITICAL",
                    reason="Initializes framework routers, middleware, and application configuration.",
                )
            )
            step += 1

        # Priority 3: API Router / Controllers
        route_files = sorted(list({ep.get("file") for ep in api_inventory if ep.get("file")}))
        for rf in route_files[:3]:
            reading_path.append(
                ReadingPathItem(
                    step=step,
                    file_path=rf,
                    title=f"API Route Handlers (`{rf.split('/')[-1]}`)",
                    importance="CORE",
                    reason="Defines HTTP endpoints, request schemas, and response contracts.",
                )
            )
            step += 1

        # Priority 4: Service / DB Layer
        db_files = [f for f in file_summaries.keys() if any(k in f.lower() for k in ("db", "model", "schema", "service"))]
        for df in db_files[:3]:
            reading_path.append(
                ReadingPathItem(
                    step=step,
                    file_path=df,
                    title=f"Data Model & Business Logic (`{df.split('/')[-1]}`)",
                    importance="CORE",
                    reason="Handles data persistence, entity definitions, and core domain rules.",
                )
            )
            step += 1

        # Fallback if few files found
        if not reading_path:
            reading_path.append(
                ReadingPathItem(
                    step=1,
                    file_path="Repository Root",
                    title="Codebase Architecture",
                    importance="CORE",
                    reason="Explore top-level directories to understand component distribution.",
                )
            )

        # ── 2. Architecture Section Summaries ─────────────────────────────────
        auth_files = [f for f in file_summaries.keys() if any(k in f.lower() for k in ("auth", "jwt", "login", "user", "security"))]
        auth_summary = (
            f"Authentication is implemented in `{auth_files[0]}` using token/session verification."
            if auth_files
            else "Authentication: Public/unrestricted endpoints or handled via standard framework middleware."
        )

        db_tech = ", ".join(tech_stack.get("databases", [])) or "SQL / Object Store"
        db_summary = (
            f"Database layer utilizes {db_tech}. "
            f"Key schema definitions reside in {', '.join([f'`{f}`' for f in db_files[:2]]) or 'the models package'}."
        )

        backend_framework = ", ".join(tech_stack.get("backend", [])) or "REST API"
        core_apis_summary = (
            f"Exposes {len(api_inventory)} REST endpoint(s) built with {backend_framework}. "
            f"Main controllers defined across {len(route_files)} route module(s)."
        )

        business_logic_summary = (
            f"Business logic is distributed across {len(module_summaries)} primary module(s): "
            + ", ".join([f"`{m}`" for m in list(module_summaries.keys())[:4]]) + "."
        )

        # ── 3. Interactive Codebase Quizzes ───────────────────────────────────
        quizzes: list[OnboardingQuiz] = []

        # Quiz 1: Entry framework
        b_fw = tech_stack.get("backend", ["FastAPI"])[0] if tech_stack.get("backend") else "Python"
        quizzes.append(
            OnboardingQuiz(
                question=f"Which primary backend framework powers {repo_name}?",
                options=[
                    OnboardingQuizOption(text=b_fw, is_correct=True),
                    OnboardingQuizOption(text="Ruby on Rails", is_correct=False),
                    OnboardingQuizOption(text="ASP.NET Core", is_correct=False),
                    OnboardingQuizOption(text="Laravel", is_correct=False),
                ],
                explanation=f"The backend tech stack detection identified {b_fw} as the primary framework.",
                citation_file=reading_path[0].file_path if reading_path else "README.md",
                citation_line=1,
            )
        )

        # Quiz 2: API Inventory count
        if api_inventory:
            first_api = api_inventory[0]
            first_path = first_api.get("path", "/health")
            first_file = first_api.get("file", "routes.py")
            quizzes.append(
                OnboardingQuiz(
                    question=f"Which file handles the endpoint `{first_path}`?",
                    options=[
                        OnboardingQuizOption(text=first_file, is_correct=True),
                        OnboardingQuizOption(text="config/settings.py", is_correct=False),
                        OnboardingQuizOption(text="utils/helpers.py", is_correct=False),
                        OnboardingQuizOption(text="static/index.html", is_correct=False),
                    ],
                    explanation=f"The API Discovery agent registered `{first_path}` inside `{first_file}`.",
                    citation_file=first_file,
                    citation_line=first_api.get("line_number") or 1,
                )
            )

        # Quiz 3: Database / Auth module
        if auth_files:
            quizzes.append(
                OnboardingQuiz(
                    question="Which module is responsible for user authentication & security?",
                    options=[
                        OnboardingQuizOption(text=auth_files[0], is_correct=True),
                        OnboardingQuizOption(text="package.json", is_correct=False),
                        OnboardingQuizOption(text="docker-compose.yml", is_correct=False),
                    ],
                    explanation=f"Security pattern detection found authentication logic in `{auth_files[0]}`.",
                    citation_file=auth_files[0],
                    citation_line=1,
                )
            )

        return ProjectOnboardingReport(
            recommended_reading_path=reading_path,
            auth_flow_summary=auth_summary,
            database_layer_summary=db_summary,
            core_apis_summary=core_apis_summary,
            business_logic_summary=business_logic_summary,
            quizzes=quizzes,
        )
