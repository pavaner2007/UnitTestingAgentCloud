"""
ArchitectureDriftAgent — validates codebase architectural integrity against design rules.

Detects direct DB access from controllers/routes, circular dependencies, layer inversion,
god files, mixed responsibilities, and missing service layer patterns without needing an LLM.
"""
from __future__ import annotations

import logging
from typing import Any

from app.schemas.v2_schemas import ArchitectureDriftReport, ArchitectureViolation

logger = logging.getLogger(__name__)


class ArchitectureDriftAgent:
    """Audits repository dependency graphs, API inventories, and file structures for architectural drift."""

    def audit(
        self,
        dependency_graph: dict[str, Any] | None,
        api_inventory: list[dict[str, Any]] | None,
        tech_stack: dict[str, Any] | None = None,
        analyzed_files: list[str] | None = None,
    ) -> ArchitectureDriftReport:
        violations: list[ArchitectureViolation] = []

        graph = dependency_graph or {}
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        cycles = graph.get("cycles", [])
        files = analyzed_files or [n.get("file") for n in nodes if n.get("file")]

        # ── Rule 1: Circular Dependencies ─────────────────────────────────────
        if cycles:
            violating_files = list({f for cycle in cycles for f in cycle})
            violations.append(
                ArchitectureViolation(
                    rule_id="CIRCULAR_DEPENDENCY",
                    title="Circular Module Dependency Cycle",
                    severity="CRITICAL",
                    violating_files=violating_files[:10],
                    reason=f"Found {len(cycles)} circular import cycle(s) in the dependency graph.",
                    expected_architecture="Dependencies should form a Directed Acyclic Graph (DAG).",
                    suggested_fix="Decouple shared types/utilities into a common module or use interface abstraction.",
                )
            )

        # ── Rule 2: Direct Database Access from Route Handlers ────────────────
        route_files = {ep.get("file") for ep in (api_inventory or []) if ep.get("file")}
        db_access_routes: list[str] = []

        for edge in edges:
            src = edge.get("from") or edge.get("from_file") or ""
            dst = edge.get("to") or edge.get("to_file") or ""
            if src in route_files and any(pattern in dst.lower() for pattern in ("db", "session", "model", "query")):
                if not any(pattern in src.lower() for pattern in ("service", "usecase", "handler")):
                    db_access_routes.append(src)

        if db_access_routes:
            violations.append(
                ArchitectureViolation(
                    rule_id="ROUTE_DIRECT_DB",
                    title="API Route Directly Accessing Database Layer",
                    severity="CRITICAL",
                    violating_files=sorted(list(set(db_access_routes)))[:10],
                    reason="API route/controller files directly import database models or DB sessions.",
                    expected_architecture="Routes should delegate business logic & DB access to a dedicated Service layer.",
                    suggested_fix="Refactor DB queries into a Service or Repository class.",
                )
            )

        # ── Rule 3: Missing Service Layer ─────────────────────────────────────
        has_routes = len(route_files) > 0
        has_services = any("service" in f.lower() for f in files)
        if has_routes and not has_services and len(files) > 5:
            violations.append(
                ArchitectureViolation(
                    rule_id="MISSING_SERVICE_LAYER",
                    title="Missing Application Service Layer",
                    severity="WARNING",
                    violating_files=sorted(list(route_files))[:5],
                    reason="Repository has API endpoints but no dedicated service modules detected.",
                    expected_architecture="Clean 3-tier architecture: Routes → Services → Repositories/Database.",
                    suggested_fix="Create a `services/` module to encapsulate domain logic.",
                )
            )

        # ── Rule 4: Layer Inversion (Frontend importing Backend or vice versa) ──
        layer_inversions: list[str] = []
        for edge in edges:
            src = edge.get("from") or edge.get("from_file") or ""
            dst = edge.get("to") or edge.get("to_file") or ""
            if ("frontend" in src.lower() or "src/components" in src.lower()) and (
                "backend" in dst.lower() or "db" in dst.lower()
            ):
                layer_inversions.append(f"{src} -> {dst}")

        if layer_inversions:
            violations.append(
                ArchitectureViolation(
                    rule_id="LAYER_INVERSION",
                    title="Layer Inversion / Boundary Leak",
                    severity="CRITICAL",
                    violating_files=layer_inversions[:10],
                    reason="Frontend UI component imports backend/database code directly.",
                    expected_architecture="Frontend and Backend should be strictly decoupled and communicate via REST/GraphQL APIs.",
                    suggested_fix="Remove direct imports and use HTTP client requests to communicate with the API.",
                )
            )

        # ── Rule 5: Mixed Responsibilities / God Files ───────────────────────
        high_dependency_files = [
            n.get("file") for n in nodes
            if n.get("dependency_count", 0) > 8
        ]
        if high_dependency_files:
            violations.append(
                ArchitectureViolation(
                    rule_id="MIXED_RESPONSIBILITIES",
                    title="High Coupling / God File Detected",
                    severity="SUGGESTION",
                    violating_files=high_dependency_files[:10],
                    reason=f"Found {len(high_dependency_files)} file(s) with high inward dependency count (>8 dependent files).",
                    expected_architecture="Modules should maintain single responsibility and low coupling.",
                    suggested_fix="Split large central files into smaller focused single-responsibility utility modules.",
                )
            )

        # Summary computation
        critical_c = sum(1 for v in violations if v.severity == "CRITICAL")
        warning_c = sum(1 for v in violations if v.severity == "WARNING")
        suggestion_c = sum(1 for v in violations if v.severity == "SUGGESTION")

        if not violations:
            summary = "Repository strictly adheres to standard architectural boundaries. No violations detected."
        else:
            summary = (
                f"Architectural drift audit found {len(violations)} issue(s): "
                f"{critical_c} Critical, {warning_c} Warning, {suggestion_c} Suggestion."
            )

        return ArchitectureDriftReport(
            total_violations=len(violations),
            critical_count=critical_c,
            warning_count=warning_c,
            suggestion_count=suggestion_c,
            violations=violations,
            summary=summary,
        )
