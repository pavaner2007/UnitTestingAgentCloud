"""
ChangeImpactAnalysisAgent — static dependency graph traversal and impact predictor.

Predicts affected files, API routes, services, modules, and models when a developer
changes a specific target file. Performs purely static graph traversal without code execution.
"""
from __future__ import annotations

import logging
from typing import Any

from app.schemas.v2_schemas import ChangeImpactResult, ImpactedFile

logger = logging.getLogger(__name__)


class ChangeImpactAnalysisAgent:
    """Predicts downstream and upstream impact of modifying a specific source file."""

    def analyze_impact(
        self,
        target_file: str,
        dependency_graph: dict[str, Any] | None,
        api_inventory: list[dict[str, Any]] | None,
    ) -> ChangeImpactResult:
        """
        Traverse dependency graph to compute impact scope of changes to `target_file`.
        """
        normal_target = self._normalise_path(target_file)
        if not dependency_graph or not isinstance(dependency_graph, dict):
            return ChangeImpactResult(
                target_file=target_file,
                impact_score=0.0,
                risk_level="LOW",
                explanation=f"No dependency graph available to evaluate impact for '{target_file}'.",
            )

        edges = dependency_graph.get("edges", [])
        nodes = dependency_graph.get("nodes", [])

        # Build adjacency lists
        # dependents: file -> list of files that import `file` (who depends on X?)
        dependents_map: dict[str, list[str]] = {}
        # dependencies: file -> list of files that `file` imports (who does X depend on?)
        dependencies_map: dict[str, list[str]] = {}

        for edge in edges:
            src = self._normalise_path(edge.get("from") or edge.get("from_file") or "")
            dst = self._normalise_path(edge.get("to") or edge.get("to_file") or "")
            if src and dst:
                dependencies_map.setdefault(src, []).append(dst)
                dependents_map.setdefault(dst, []).append(src)

        # BFS for direct & transitive dependents (files that will break if target changes)
        visited_dependents: dict[str, int] = {}  # file -> min_distance
        queue = [(normal_target, 0)]
        visited_set = {normal_target}

        while queue:
            curr, dist = queue.pop(0)
            if dist > 0:
                visited_dependents[curr] = dist
            if dist < 3:  # Max 3-hop depth
                for dep in dependents_map.get(curr, []):
                    if dep not in visited_set:
                        visited_set.add(dep)
                        queue.append((dep, dist + 1))

        # BFS for direct dependencies (files target relies on)
        visited_dependencies: dict[str, int] = {}
        dep_queue = [(normal_target, 0)]
        dep_visited = {normal_target}

        while dep_queue:
            curr, dist = dep_queue.pop(0)
            if dist > 0:
                visited_dependencies[curr] = dist
            if dist < 2:
                for dep in dependencies_map.get(curr, []):
                    if dep not in dep_visited:
                        dep_visited.add(dep)
                        dep_queue.append((dep, dist + 1))

        # Build impacted files list
        impacted_files: list[ImpactedFile] = []
        for file_path, dist in visited_dependents.items():
            risk_score = round(max(0.1, 1.0 - (dist - 1) * 0.3), 2)
            impacted_files.append(
                ImpactedFile(
                    file_path=file_path,
                    distance=dist,
                    impact_type="direct_dependent" if dist == 1 else "transitive_dependent",
                    risk_score=risk_score,
                )
            )

        # Classify affected components
        all_affected = {normal_target} | set(visited_dependents.keys()) | set(visited_dependencies.keys())

        impacted_routes: list[str] = []
        if api_inventory:
            for ep in api_inventory:
                ep_file = self._normalise_path(ep.get("file") or "")
                if ep_file in all_affected:
                    method = ep.get("method", "GET")
                    path = ep.get("path", "/")
                    route_str = f"{method} {path} ({ep_file})"
                    if route_str not in impacted_routes:
                        impacted_routes.append(route_str)

        impacted_services: list[str] = []
        impacted_modules: set[str] = set()
        impacted_models: list[str] = []

        for path in all_affected:
            parts = path.split("/")
            if len(parts) > 1:
                impacted_modules.add(parts[0])

            lower = path.lower()
            if "service" in lower:
                impacted_services.append(path)
            elif "model" in lower or "schema" in lower or "db" in lower:
                impacted_models.append(path)

        # Calculate overall Impact Score (0 - 100)
        dep_count = len(visited_dependents)
        route_count = len(impacted_routes)
        in_degree = sum(1 for n in nodes if self._normalise_path(n.get("file") or "") == normal_target)

        raw_score = (dep_count * 15) + (route_count * 20) + (in_degree * 5)
        impact_score = min(100.0, round(float(raw_score), 1))

        if impact_score >= 75.0 or "auth" in normal_target.lower() or "config" in normal_target.lower():
            risk_level = "CRITICAL"
        elif impact_score >= 45.0:
            risk_level = "HIGH"
        elif impact_score >= 20.0:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        explanation = (
            f"Modifying '{target_file}' directly or transitively affects {dep_count} file(s) "
            f"and {route_count} API route(s). Change risk level is rated {risk_level} "
            f"with an impact score of {impact_score}/100."
        )

        return ChangeImpactResult(
            target_file=target_file,
            impact_score=impact_score,
            risk_level=risk_level,
            impacted_files=impacted_files,
            impacted_routes=impacted_routes,
            impacted_services=sorted(impacted_services),
            impacted_modules=sorted(list(impacted_modules)),
            impacted_models=sorted(impacted_models),
            explanation=explanation,
        )

    @staticmethod
    def _normalise_path(p: str) -> str:
        return p.strip().replace("\\", "/").lstrip("/")
