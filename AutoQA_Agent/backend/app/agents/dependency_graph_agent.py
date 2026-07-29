"""
DependencyGraphAgent — parses file import statements and computes a directed dependency graph.

Design:
- Pure Python & AST/regex parsing — deterministic, zero LLM cost.
- Runs over ALL scannable source files in the repo (not the LLM-budget subset),
  because import parsing is cheap and the full graph is more accurate.
- Supports Python (`import x`, `from x import y`, `from . import z`) and
  JS/TS (`import ... from '...'`, `require('...')`).
- Computes:
    · nodes: list of {file, dependency_count (in-degree)}
    · edges: list of {from_file, to_file}
    · cycles: list of file lists representing circular dependency paths (DFS)
    · most_depended_on: file path with the highest in-degree (or None)
"""
from __future__ import annotations

import ast
import logging
import os
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── JS/TS import regex ────────────────────────────────────────────────────────
# Matches: import ... from 'path'  |  require('path')
_RE_JS_IMPORT = re.compile(
    r"""(?:import\s+(?:.*?\s+from\s+)?['\"]([^'"]+)['\"]|require\s*\(\s*['\"]([^'"]+)['\"])""",
    re.MULTILINE,
)

# Scannable source extensions for the full-repo pass
_SCANNABLE = frozenset({".py", ".js", ".jsx", ".ts", ".tsx"})

# Dirs to skip when walking the full repo
_EXCLUDED_DIRS = frozenset({
    "node_modules", ".git", "venv", ".venv", "vendor", "dist", "build",
    "target", "__pycache__", ".next", ".nuxt", "coverage", "htmlcov",
    ".pytest_cache", ".mypy_cache", ".cache", "tmp", "temp",
    ".github", ".gitlab",
})


def _collect_all_source_files(repo_path: Path) -> list[Path]:
    """
    Walk the repo and return every source file with a scannable extension,
    excluding vendor/build directories and files > 300 KB.
    This is intentionally broader than FilePrioritizationAgent's budget-capped set.
    """
    result: list[Path] = []
    for root, dirs, files in os.walk(repo_path):
        # Prune excluded directories in-place so os.walk won't descend into them
        dirs[:] = [d for d in dirs if d not in _EXCLUDED_DIRS]
        for fname in files:
            fp = Path(root) / fname
            if fp.suffix.lower() not in _SCANNABLE:
                continue
            try:
                if fp.stat().st_size > 300_000:
                    continue
            except OSError:
                continue
            result.append(fp)
    return result


def _normalize_js_import(imp: str, file_rel: str, known_files: set[str]) -> str | None:
    """
    Resolve a JS/TS relative import specifier to a known file's relative path.

    Key invariant: we work entirely with repo-relative paths (forward-slash,
    no leading ./), so we never call Path.resolve() against the real filesystem.
    """
    if not imp.startswith("."):
        return None   # Third-party package — skip

    # Compute the directory of the importing file (repo-relative, forward-slash)
    file_dir = "/".join(file_rel.replace("\\", "/").split("/")[:-1])

    # Walk the relative import manually (handles ../ correctly)
    parts = (file_dir + "/" + imp).split("/") if file_dir else imp.split("/")
    normalized: list[str] = []
    for part in parts:
        if part == "..":
            if normalized:
                normalized.pop()
        elif part and part != ".":
            normalized.append(part)
    base = "/".join(normalized)

    # Try common JS module resolutions in priority order
    for cand in (
        base,
        base + ".js",
        base + ".jsx",
        base + ".ts",
        base + ".tsx",
        base + "/index.js",
        base + "/index.jsx",
        base + "/index.ts",
        base + "/index.tsx",
    ):
        if cand in known_files:
            return cand
    return None


def _normalize_py_import(imp: str, known_files: set[str]) -> list[str]:
    """
    Map a Python import string to zero or more known file paths.
    Returns a list because `import a, b, c` can resolve to multiple files.
    """
    targets: list[str] = []
    # Handle comma-separated: `import os, sys, mymod`
    for part in imp.split(","):
        part = part.strip().split(" ")[0]   # strip trailing ' as alias'
        if not part:
            continue
        target_base = part.replace(".", "/")
        for cand in (f"{target_base}.py", f"{target_base}/__init__.py"):
            if cand in known_files:
                targets.append(cand)
                break
            # Suffix match (handles sub-package paths)
            for kf in known_files:
                if kf == cand or kf.endswith("/" + cand):
                    targets.append(kf)
                    break
    return targets


def _parse_python_imports(content: str, file_rel: str, known_files: set[str]) -> set[str]:
    """
    Use Python's `ast` module for precise import parsing, with a regex fallback.
    Returns a set of repo-relative file paths that this file imports.
    """
    deps: set[str] = set()
    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for t in _normalize_py_import(alias.name, known_files):
                        if t != file_rel:
                            deps.add(t)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    # Relative imports: `from . import x` / `from ..pkg import y`
                    if node.level and node.level > 0:
                        # Build the absolute module path from relative
                        parts = file_rel.replace("\\", "/").split("/")[:-1]
                        for _ in range(node.level - 1):
                            if parts:
                                parts.pop()
                        base_mod = ".".join(parts).replace("/", ".")
                        full_mod = (base_mod + "." + node.module) if base_mod else node.module
                    else:
                        full_mod = node.module
                    for t in _normalize_py_import(full_mod, known_files):
                        if t != file_rel:
                            deps.add(t)
        return deps
    except SyntaxError:
        # Fallback to regex for invalid-syntax files (e.g. Python 2)
        pat = re.compile(r"^\s*(?:from\s+([\w\.]+)\s+import|import\s+([\w\.,\s]+))", re.MULTILINE)
        for m in pat.finditer(content):
            imp_module = m.group(1) or m.group(2)
            if imp_module:
                for t in _normalize_py_import(imp_module, known_files):
                    if t != file_rel:
                        deps.add(t)
        return deps


class DependencyGraphAgent:
    """Build file-level dependency graph and detect circular import cycles."""

    def build_graph(
        self,
        repo_path: Path,
        file_paths: list[Path] | None = None,
    ) -> dict[str, Any]:
        """
        Build dependency graph.

        If `file_paths` is provided it is used as the seed list of files to
        *parse imports FROM*.  However, the known-files set (what we try to
        resolve imports TO) is always the full set of scannable source files so
        that cross-module edges are captured correctly even when the LLM budget
        limited which files were summarised.

        When `file_paths` is None the agent discovers all source files itself.

        Returns dict matching the DependencyGraph schema:
        {
          "nodes": [{"file": "app/main.py", "dependency_count": 5}, ...],
          "edges": [{"from_file": "app/main.py", "to_file": "app/db.py"}, ...],
          "cycles": [["app/a.py", "app/b.py", "app/a.py"]],
          "most_depended_on": "app/db.py"
        }
        """
        # ── Step 1: full-repo file discovery ─────────────────────────────────
        all_source_files = _collect_all_source_files(repo_path)

        def to_rel(fp: Path) -> str:
            try:
                return fp.relative_to(repo_path).as_posix()
            except ValueError:
                return fp.name

        known_files: set[str] = {to_rel(fp) for fp in all_source_files}
        all_file_map: dict[str, Path] = {to_rel(fp): fp for fp in all_source_files}

        # ── Step 2: which files to parse imports FROM ─────────────────────────
        # Always parse ALL source files (import parsing is free — no LLM).
        parse_files = all_file_map   # parse every source file we found

        # ── Step 3: Parse imports from every file ─────────────────────────────
        adj: dict[str, set[str]] = {f: set() for f in known_files}
        in_degree: dict[str, int] = {f: 0 for f in known_files}

        for rel, fp in parse_files.items():
            try:
                content = fp.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            suffix = fp.suffix.lower()

            if suffix == ".py":
                for target in _parse_python_imports(content, rel, known_files):
                    adj[rel].add(target)

            elif suffix in (".js", ".jsx", ".ts", ".tsx"):
                for m in _RE_JS_IMPORT.finditer(content):
                    imp_path = m.group(1) or m.group(2)
                    if not imp_path:
                        continue
                    target = _normalize_js_import(imp_path, rel, known_files)
                    if target and target != rel:
                        adj[rel].add(target)

        # ── Step 4: Compute edges & in-degree ─────────────────────────────────
        edges: list[dict[str, str]] = []
        for src, targets in adj.items():
            for tgt in sorted(targets):
                edges.append({"from_file": src, "to_file": tgt})
                in_degree[tgt] = in_degree.get(tgt, 0) + 1

        # ── Step 5: Nodes (only files with at least 1 edge, or high in-degree) ─
        # Include ALL discovered nodes (callers filter display-only)
        nodes = [
            {"file": f, "dependency_count": in_degree.get(f, 0)}
            for f in known_files
        ]
        nodes.sort(key=lambda n: (-n["dependency_count"], n["file"]))

        most_depended = (
            nodes[0]["file"]
            if nodes and nodes[0]["dependency_count"] > 0
            else None
        )

        # ── Step 6: Cycle detection (DFS) ─────────────────────────────────────
        cycles = self._find_cycles_dfs(adj)

        logger.info(
            "DependencyGraphAgent: %d nodes, %d edges, %d cycle(s) — full-repo scan",
            len(nodes), len(edges), len(cycles),
        )

        return {
            "nodes": nodes,
            "edges": edges,
            "cycles": cycles,
            "most_depended_on": most_depended,
        }

    # ── Cycle detection ────────────────────────────────────────────────────────

    def _find_cycles_dfs(self, adj: dict[str, set[str]]) -> list[list[str]]:
        """DFS cycle detection — returns up to 10 unique circular dependency paths."""
        visited: set[str] = set()
        rec_stack: list[str] = []
        cycles: list[list[str]] = []
        seen_cycle_keys: set[tuple[str, ...]] = set()

        def dfs(node: str) -> None:
            visited.add(node)
            rec_stack.append(node)
            for neighbor in sorted(adj.get(node, [])):
                if neighbor in rec_stack:
                    idx = rec_stack.index(neighbor)
                    cycle_path = rec_stack[idx:] + [neighbor]
                    key = tuple(cycle_path)
                    if key not in seen_cycle_keys:
                        seen_cycle_keys.add(key)
                        cycles.append(cycle_path)
                elif neighbor not in visited:
                    dfs(neighbor)
            rec_stack.pop()

        for n in sorted(adj):
            if n not in visited:
                dfs(n)

        return cycles[:10]
