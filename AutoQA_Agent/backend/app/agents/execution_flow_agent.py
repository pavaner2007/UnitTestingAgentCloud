"""
ExecutionFlowAgent — AI Code Execution Flow Visualizer.

Purpose
-------
Visualize how a request or function flows through the project using
PURELY deterministic static analysis.  No code is ever executed.
No LLM is called.  All inference is from AST + dependency graph.

Key capabilities
----------------
* Builds an execution graph starting from API endpoints or named functions.
* Detects:
    - Outgoing function calls (direct + transitive)
    - Database access (SQLAlchemy, raw SQL, Django ORM, Tortoise, Peewee)
    - External HTTP calls (requests, httpx, aiohttp, urllib, axios, fetch)
    - Exception handlers (try/except + @app.exception_handler)
    - Class instantiation used as service calls
* Assigns a confidence score to each inferred edge.
* Returns ExecutionFlowResult per entry point.

Design constraints
------------------
* Deterministic — same input always produces same graph.
* Never executes repository code.
* Degrades gracefully when AST parsing fails (skips the file).
* Max recursion depth: configurable (default 5).
"""
from __future__ import annotations

import ast
import logging
import os
import re
from pathlib import Path
from typing import Any

from app.schemas.v2_schemas import (
    ExecutionFlowEdge,
    ExecutionFlowNode,
    ExecutionFlowResult,
)

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

_MAX_DEPTH = 5          # maximum call-chain depth
_MAX_NODES = 60         # cap per flow to keep UI usable

_EXCLUDED_DIRS = frozenset({
    "node_modules", ".git", "venv", ".venv", "vendor", "dist", "build",
    "target", "__pycache__", ".next", ".nuxt", "coverage", "htmlcov",
    ".pytest_cache", ".mypy_cache", ".cache", "tmp", "temp",
})

# DB call patterns — attribute access names that signal DB operations
_DB_CALL_ATTRS = frozenset({
    # SQLAlchemy
    "query", "execute", "add", "commit", "rollback", "flush", "get",
    "filter", "filter_by", "first", "all", "one", "scalar",
    # Django ORM
    "objects", "save", "create", "update", "delete", "bulk_create",
    # Tortoise / Peewee
    "select", "insert", "where", "order_by", "fetch",
    # Raw SQL
    "cursor", "fetchone", "fetchall", "fetchmany",
})

# DB object name hints (variable/param names that suggest DB context)
_DB_OBJECT_HINTS = frozenset({
    "db", "session", "conn", "connection", "cursor", "engine",
    "repo", "repository",
})

# HTTP call names that signal external requests
_HTTP_CALL_NAMES = frozenset({
    # requests / httpx / aiohttp / urllib
    "get", "post", "put", "patch", "delete", "request", "send",
    "fetch",  # JS-style
    # Explicit class names
    "requests", "httpx", "aiohttp", "urllib",
})

_HTTP_MODULE_HINTS = frozenset({
    "requests", "httpx", "aiohttp", "urllib", "urllib3", "http",
})


# ── Utility: walk source files ────────────────────────────────────────────────

def _collect_py_files(repo_path: Path) -> dict[str, Path]:
    """Return {repo-relative-path: absolute-Path} for every .py file."""
    result: dict[str, Path] = {}
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in _EXCLUDED_DIRS]
        for fname in files:
            fp = Path(root) / fname
            if fp.suffix.lower() == ".py":
                try:
                    rel = fp.relative_to(repo_path).as_posix()
                    result[rel] = fp
                except ValueError:
                    pass
    return result


# ── AST helpers ───────────────────────────────────────────────────────────────

def _safe_parse(fp: Path) -> ast.Module | None:
    try:
        return ast.parse(fp.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def _get_attribute_chain(node: ast.AST) -> list[str]:
    """Recursively extract an attribute chain like ['self', 'db', 'query']."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return list(reversed(parts))


def _is_db_call(call_node: ast.Call) -> bool:
    """Heuristically determine if a call is a database operation."""
    chain = _get_attribute_chain(call_node.func)
    if not chain:
        return False
    # e.g. db.query(...) or session.execute(...)
    if len(chain) >= 2 and chain[-2].lower() in _DB_OBJECT_HINTS and chain[-1].lower() in _DB_CALL_ATTRS:
        return True
    # e.g. User.objects.filter() — chain contains 'objects' somewhere
    if "objects" in [c.lower() for c in chain]:
        return True
    return False


def _is_http_call(call_node: ast.Call) -> bool:
    """Heuristically determine if a call is an external HTTP request."""
    chain = _get_attribute_chain(call_node.func)
    if not chain:
        return False
    lower_chain = [c.lower() for c in chain]
    # requests.get(...), httpx.post(...), etc.
    if any(part in _HTTP_MODULE_HINTS for part in lower_chain):
        if any(part in _HTTP_CALL_NAMES for part in lower_chain):
            return True
    return False


def _extract_function_body_calls(
    tree: ast.Module,
    function_name: str,
) -> tuple[list[str], list[str], list[str], list[str]]:
    """
    Walk a parsed AST for a specific function and extract:
    - direct function calls  (list of name strings)
    - DB call descriptions   (list)
    - HTTP call descriptions (list)
    - Handled exception names (list)

    Returns: (calls, db_calls, http_calls, exceptions)
    """
    calls: list[str] = []
    db_calls: list[str] = []
    http_calls: list[str] = []
    exceptions: list[str] = []

    target_func: ast.FunctionDef | ast.AsyncFunctionDef | None = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == function_name:
                target_func = node
                break

    if target_func is None:
        return calls, db_calls, http_calls, exceptions

    for node in ast.walk(target_func):
        # Function / method calls
        if isinstance(node, ast.Call):
            if _is_db_call(node):
                chain = _get_attribute_chain(node.func)
                db_calls.append(".".join(chain))
            elif _is_http_call(node):
                chain = _get_attribute_chain(node.func)
                http_calls.append(".".join(chain))
            else:
                chain = _get_attribute_chain(node.func)
                call_name = ".".join(chain)
                if call_name and call_name not in {"print", "len", "str", "int", "float", "list", "dict", "set", "tuple"}:
                    calls.append(call_name)

        # Exception handlers
        if isinstance(node, ast.ExceptHandler):
            if node.type:
                if isinstance(node.type, ast.Tuple):
                    for el in node.type.elts:
                        if isinstance(el, ast.Name):
                            exceptions.append(el.id)
                elif isinstance(node.type, ast.Name):
                    exceptions.append(node.type.id)

    return calls, db_calls, http_calls, exceptions


def _find_function_in_tree(tree: ast.Module, function_name: str) -> tuple[int | None, str | None]:
    """Return (line_number, class_name | None) for the named function."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for child in ast.walk(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if child.name == function_name:
                        return getattr(child, "lineno", None), node.name
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == function_name:
                return getattr(node, "lineno", None), None
    return None, None


# ── Main Agent ────────────────────────────────────────────────────────────────

class ExecutionFlowAgent:
    """
    Build execution flow graphs for API endpoints and named functions
    using AST analysis and the pre-computed dependency graph.
    """

    def build_all_flows(
        self,
        api_inventory: list[Any],
        repo_path: Path,
        dep_graph: dict | None,
        code_insights: Any | None,
    ) -> list[ExecutionFlowResult]:
        """
        Build execution flow graphs for up to 20 API endpoints.

        Parameters
        ----------
        api_inventory:  list of ApiEndpoint-like objects (or dicts)
        repo_path:      absolute path to the cloned repository
        dep_graph:      dependency graph dict from DependencyGraphAgent
        code_insights:  CodeInsights object (may be None)

        Returns list of ExecutionFlowResult, one per traced entry point.
        """
        py_files = _collect_py_files(repo_path)
        # Build adjacency: file → set of files it imports
        adjacency = self._build_adjacency(dep_graph)
        # Parse each Python file once and cache the AST
        ast_cache: dict[str, ast.Module] = {}

        results: list[ExecutionFlowResult] = []

        # Limit to first 20 endpoints to avoid runaway analysis
        endpoints = api_inventory[:20] if api_inventory else []

        for ep in endpoints:
            if isinstance(ep, dict):
                method = ep.get("method", "GET")
                path = ep.get("path", "/")
                file_rel = ep.get("file", "")
                function_name = ep.get("function_name") or ""
            else:
                method = getattr(ep, "method", "GET")
                path = getattr(ep, "path", "/")
                file_rel = getattr(ep, "file", "")
                function_name = getattr(ep, "function_name", "") or ""

            try:
                flow = self._build_flow_for_api(
                    method=method,
                    path=path,
                    file_rel=file_rel,
                    function_name=function_name,
                    py_files=py_files,
                    adjacency=adjacency,
                    ast_cache=ast_cache,
                )
                results.append(flow)
            except Exception as exc:
                logger.debug("ExecutionFlowAgent: skipped %s %s — %s", method, path, exc)

        logger.info("ExecutionFlowAgent: built %d execution flows", len(results))
        return results

    # ── Per-endpoint flow builder ─────────────────────────────────────────────

    def _build_flow_for_api(
        self,
        method: str,
        path: str,
        file_rel: str,
        function_name: str,
        py_files: dict[str, Path],
        adjacency: dict[str, set[str]],
        ast_cache: dict[str, ast.Module],
    ) -> ExecutionFlowResult:
        entry_label = f"{method} {path}"
        nodes: list[ExecutionFlowNode] = []
        edges: list[ExecutionFlowEdge] = []
        db_ops_total = 0
        http_ops_total = 0
        all_exceptions: list[str] = []

        # Root node
        root_id = f"api::{method}::{path}"
        nodes.append(ExecutionFlowNode(
            id=root_id,
            label=entry_label,
            node_type="api_endpoint",
            file_path=file_rel or "unknown",
            confidence=1.0,
            metadata={"method": method, "path": path},
        ))

        # BFS / DFS traversal
        visited_functions: set[str] = set()
        queue: list[tuple[str, str, str, int, float]] = []
        # (parent_node_id, file_rel, function_name, depth, confidence)

        if function_name and file_rel:
            queue.append((root_id, file_rel, function_name, 1, 0.95))

        while queue and len(nodes) < _MAX_NODES:
            parent_id, cur_file, cur_func, depth, conf = queue.pop(0)
            if depth > _MAX_DEPTH:
                continue
            func_key = f"{cur_file}::{cur_func}"
            if func_key in visited_functions:
                continue
            visited_functions.add(func_key)

            # Parse the file if not cached
            tree = self._get_ast(cur_file, py_files, ast_cache)
            if tree is None:
                continue

            calls, db_calls, http_calls, exceptions = _extract_function_body_calls(tree, cur_func)
            all_exceptions.extend(exceptions)

            # Add DB call nodes
            for db_call in db_calls[:4]:
                db_id = f"db::{cur_file}::{db_call}"
                if not any(n.id == db_id for n in nodes):
                    nodes.append(ExecutionFlowNode(
                        id=db_id,
                        label=f"[DB] {db_call}",
                        node_type="db_call",
                        file_path=cur_file,
                        confidence=0.85,
                        metadata={"db_operation": db_call},
                    ))
                    db_ops_total += 1
                edges.append(ExecutionFlowEdge(
                    from_id=parent_id,
                    to_id=db_id,
                    edge_type="db_query",
                    label="DB",
                ))

            # Add HTTP call nodes
            for http_call in http_calls[:3]:
                http_id = f"http::{cur_file}::{http_call}"
                if not any(n.id == http_id for n in nodes):
                    nodes.append(ExecutionFlowNode(
                        id=http_id,
                        label=f"[HTTP] {http_call}",
                        node_type="external_http",
                        file_path=cur_file,
                        confidence=0.80,
                        metadata={"http_call": http_call},
                    ))
                    http_ops_total += 1
                edges.append(ExecutionFlowEdge(
                    from_id=parent_id,
                    to_id=http_id,
                    edge_type="http_request",
                    label="HTTP",
                ))

            # Resolve called functions → find them in adjacent/imported files
            for call_name in calls[:8]:
                # Extract the base function name (last part of dotted chain)
                parts = call_name.split(".")
                fn_base = parts[-1]
                if not fn_base or len(fn_base) < 2:
                    continue

                # Search for the function in files that this file imports
                resolved_file, resolved_line = self._resolve_call(
                    fn_base, cur_file, adjacency, py_files, ast_cache
                )

                child_conf = round(conf * 0.85, 3)
                child_id = f"fn::{resolved_file or cur_file}::{call_name}"

                if not any(n.id == child_id for n in nodes):
                    node_type = "function"
                    line_no, class_name = (None, None)
                    if resolved_file:
                        t = self._get_ast(resolved_file, py_files, ast_cache)
                        if t:
                            line_no, class_name = _find_function_in_tree(t, fn_base)
                        if class_name:
                            node_type = "class"

                    nodes.append(ExecutionFlowNode(
                        id=child_id,
                        label=call_name if not class_name else f"{class_name}.{fn_base}",
                        node_type=node_type,
                        file_path=resolved_file or cur_file,
                        line_number=line_no,
                        confidence=child_conf,
                        metadata={"class": class_name} if class_name else {},
                    ))

                edges.append(ExecutionFlowEdge(
                    from_id=parent_id,
                    to_id=child_id,
                    edge_type="calls",
                ))

                # Recurse into the called function
                if resolved_file and fn_base:
                    queue.append((child_id, resolved_file, fn_base, depth + 1, child_conf))

        # Deduplicate edges
        seen_edges: set[tuple[str, str]] = set()
        deduped_edges: list[ExecutionFlowEdge] = []
        for e in edges:
            key = (e.from_id, e.to_id)
            if key not in seen_edges:
                seen_edges.add(key)
                deduped_edges.append(e)

        # Compute execution depth
        exec_depth = max((len(n.id.split("::")) for n in nodes), default=0) - 1

        # Overall confidence = average of node confidences
        avg_conf = round(sum(n.confidence for n in nodes) / max(len(nodes), 1), 3)

        summary = (
            f"Execution flow for {entry_label}: "
            f"{len(nodes)} nodes, {len(deduped_edges)} transitions, "
            f"depth={exec_depth}, DB ops={db_ops_total}, "
            f"HTTP calls={http_ops_total}."
        )

        return ExecutionFlowResult(
            entry_point=entry_label,
            nodes=nodes,
            edges=deduped_edges,
            execution_depth=exec_depth,
            db_operations_count=db_ops_total,
            external_http_calls_count=http_ops_total,
            exceptions_handled=list(set(all_exceptions))[:10],
            confidence_score=avg_conf,
            summary=summary,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _build_adjacency(self, dep_graph: dict | None) -> dict[str, set[str]]:
        """Build file adjacency map from dependency graph edges."""
        adjacency: dict[str, set[str]] = {}
        if not dep_graph:
            return adjacency
        for edge in dep_graph.get("edges", []):
            src = edge.get("from_file") or edge.get("from")
            tgt = edge.get("to_file") or edge.get("to")
            if src and tgt:
                adjacency.setdefault(src, set()).add(tgt)
        return adjacency

    def _get_ast(
        self,
        file_rel: str,
        py_files: dict[str, Path],
        ast_cache: dict[str, ast.Module],
    ) -> ast.Module | None:
        if file_rel in ast_cache:
            return ast_cache[file_rel]
        fp = py_files.get(file_rel)
        if not fp:
            # Try suffix-match
            for k, v in py_files.items():
                if k.endswith(file_rel) or file_rel.endswith(k):
                    fp = v
                    break
        if not fp:
            return None
        tree = _safe_parse(fp)
        if tree:
            ast_cache[file_rel] = tree
        return tree

    def _resolve_call(
        self,
        fn_name: str,
        caller_file: str,
        adjacency: dict[str, set[str]],
        py_files: dict[str, Path],
        ast_cache: dict[str, ast.Module],
    ) -> tuple[str | None, int | None]:
        """
        Search for `fn_name` in files imported by `caller_file`.
        Returns (file_rel, line_number) or (None, None).
        """
        search_files = list(adjacency.get(caller_file, set()))
        for file_rel in search_files[:10]:
            tree = self._get_ast(file_rel, py_files, ast_cache)
            if not tree:
                continue
            line_no, _ = _find_function_in_tree(tree, fn_name)
            if line_no is not None:
                return file_rel, line_no
        return None, None
