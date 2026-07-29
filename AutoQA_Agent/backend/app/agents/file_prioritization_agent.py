"""
FilePrioritizationAgent — ranks cloned repository files so only the most
architecturally significant ones are sent to the code-analysis stage.

Design goals
------------
- Pure Python, zero LLM calls — all scoring is deterministic.
- Enforces MAX_FILES_TO_ANALYZE and MAX_CODE_TOKEN_BUDGET (settings).
- Degrades gracefully on malformed paths / permission errors.
- Exposes skip reasons per file so callers can surface them in reports/logs.

Scoring logic (higher = more important)
---------------------------------------
  +50  known entry-point filename (main.py, app.py, server.js, …)
  +40  directory flagged by api_discovery_agent as containing routes
  +30  architecturally significant directory name (models/, services/, db/, …)
  +15  test file (test_*, *_test.py, *.spec.ts) — analyzed if budget allows
  +5   config file (.yaml, .toml, Makefile, …) — analyzed if budget allows
  + 0  everything else (still eligible unless excluded)
  excluded → skipped entirely (node_modules, .git, vendor, dist, lockfiles, binaries)

Skip reason codes
-----------------
  "selected"               → passed all filters, within budget
  "excluded_vendor"        → inside node_modules, vendor, dist, build, etc.
  "excluded_binary"        → binary/minified extension or oversized file
  "excluded_lockfile"      → known lockfile (package-lock.json, etc.)
  "excluded_token_budget"  → would have been selected but token budget exhausted
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Exclusion lists ────────────────────────────────────────────────────────────

_EXCLUDED_DIRS = frozenset({
    "node_modules", ".git", "venv", ".venv", "vendor", "dist", "build",
    "target", "__pycache__", ".next", ".nuxt", "coverage", "htmlcov",
    ".pytest_cache", ".mypy_cache", ".tox", ".eggs", "eggs", ".cache",
    "tmp", "temp", ".github", ".gitlab",
})

_EXCLUDED_EXTENSIONS = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp", ".bmp", ".tiff",
    ".mp4", ".mp3", ".mov", ".wav", ".ogg",
    ".ttf", ".woff", ".woff2", ".eot", ".otf",
    ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar",
    ".pdf", ".docx", ".xlsx", ".pptx",
    ".pyc", ".pyo", ".class", ".o", ".so", ".dll", ".exe", ".dylib",
    ".min.js", ".min.css", ".bundle.js", ".map",
})

_EXCLUDED_FILENAMES = frozenset({
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "poetry.lock", "Pipfile.lock", "Gemfile.lock",
    "composer.lock", "Cargo.lock", "go.sum",
    ".DS_Store", "Thumbs.db",
})

# ── Priority boosts ────────────────────────────────────────────────────────────

_ENTRY_POINT_NAMES = frozenset({
    "main.py", "app.py", "server.py", "wsgi.py", "asgi.py",
    "index.js", "server.js", "app.js", "index.ts", "server.ts",
    "main.go", "main.java", "main.rb", "application.py",
    "manage.py", "cli.py",
})

_ARCH_SIGNIFICANT_DIRS = frozenset({
    "models", "model", "routes", "route", "controllers", "controller",
    "services", "service", "db", "database", "repositories", "repository",
    "handlers", "handler", "middleware", "auth", "api", "core", "domain",
    "schemas", "schema", "views", "resolvers",
})

_CONFIG_EXTENSIONS = frozenset({
    ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".env.example", ".env.sample",
})

_CONFIG_FILENAMES = frozenset({
    "Makefile", "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
    ".eslintrc.js", ".babelrc", "jest.config.js", "tsconfig.json",
    "webpack.config.js", "vite.config.ts", "vite.config.js",
})


# ── Data classes ───────────────────────────────────────────────────────────────

@dataclass
class PrioritizedFile:
    path: Path
    priority_score: int
    reason: str
    estimated_tokens: int = 0
    status: str = "selected"
    # status values:
    #   "selected"              → within budget, will be analyzed
    #   "excluded_vendor"       → inside vendor/node_modules/build dirs
    #   "excluded_binary"       → binary extension or oversized (>200 KB)
    #   "excluded_lockfile"     → known lockfile
    #   "excluded_token_budget" → would be selected but budget exhausted


@dataclass
class PrioritizationResult:
    """Return value of FilePrioritizationAgent.prioritize()."""
    selected: list[PrioritizedFile]
    skipped_breakdown: dict[str, int]
    # e.g. {"excluded_vendor": 20, "excluded_token_budget": 5, "excluded_binary": 3}


# ── Agent ─────────────────────────────────────────────────────────────────────

class FilePrioritizationAgent:
    """Rank and filter source files from a cloned repository."""

    def prioritize(
        self,
        repo_path: Path,
        all_files: list[Path] | None = None,
        route_files: set[str] | None = None,
    ) -> PrioritizationResult:
        """
        Returns PrioritizationResult:
          .selected          — ranked list truncated to budget
          .skipped_breakdown — count per skip-reason code
        """
        route_files = route_files or set()

        if all_files is None:
            try:
                all_files = list(repo_path.rglob("*"))
            except Exception as exc:
                logger.warning("Could not enumerate repo files: %s", exc)
                return PrioritizationResult(selected=[], skipped_breakdown={})

        scored: list[PrioritizedFile] = []
        skipped_breakdown: dict[str, int] = {}

        for file_path in all_files:
            if not file_path.is_file():
                continue
            try:
                pf, skip_code = self._score(file_path, repo_path, route_files)
            except Exception:
                continue

            if skip_code:
                skipped_breakdown[skip_code] = skipped_breakdown.get(skip_code, 0) + 1
            else:
                scored.append(pf)  # type: ignore[arg-type]

        scored.sort(key=lambda pf: (-pf.priority_score, len(str(pf.path))))

        selected: list[PrioritizedFile] = []
        token_total = 0
        for pf in scored:
            if len(selected) >= settings.max_files_to_analyze:
                skipped_breakdown["excluded_token_budget"] = (
                    skipped_breakdown.get("excluded_token_budget", 0) + 1
                )
                pf.status = "excluded_token_budget"
                continue
            if token_total + pf.estimated_tokens > settings.max_code_token_budget:
                logger.debug("Token budget exhausted — skipping %s", pf.path.name)
                skipped_breakdown["excluded_token_budget"] = (
                    skipped_breakdown.get("excluded_token_budget", 0) + 1
                )
                pf.status = "excluded_token_budget"
                continue
            pf.status = "selected"
            selected.append(pf)
            token_total += pf.estimated_tokens

        total_considered = len(scored) + sum(skipped_breakdown.values())
        logger.info(
            "FilePrioritization: %d/%d files selected (~%d tokens, budget %d)",
            len(selected), total_considered, token_total, settings.max_code_token_budget,
        )
        logger.info("FilePrioritization skip breakdown: %s", skipped_breakdown)
        return PrioritizationResult(selected=selected, skipped_breakdown=skipped_breakdown)

    # ── Internals ─────────────────────────────────────────────────────────────

    def _score(
        self,
        file_path: Path,
        repo_root: Path,
        route_files: set[str],
    ) -> tuple[PrioritizedFile | None, str | None]:
        """(PrioritizedFile, None) for eligible; (None, skip_code) for excluded."""
        try:
            rel = file_path.relative_to(repo_root)
        except ValueError:
            return None, "excluded_binary"

        parts = rel.parts
        name = file_path.name
        suffix = file_path.suffix.lower()
        rel_str = str(rel)

        # ── Exclusions ──────────────────────────────────────────────────────
        if any(part in _EXCLUDED_DIRS for part in parts[:-1]):
            return None, "excluded_vendor"
        if name in _EXCLUDED_FILENAMES:
            return None, "excluded_lockfile"
        if suffix in _EXCLUDED_EXTENSIONS:
            return None, "excluded_binary"
        for bad_ext in (".min.js", ".min.css", ".bundle.js"):
            if name.endswith(bad_ext):
                return None, "excluded_binary"
        try:
            if file_path.stat().st_size > 200_000:
                return None, "excluded_binary"
        except OSError:
            return None, "excluded_binary"

        # ── Scoring ─────────────────────────────────────────────────────────
        score = 0
        reasons: list[str] = []

        if name in _ENTRY_POINT_NAMES:
            score += 50
            reasons.append("entry point")

        if rel_str in route_files or any(part in route_files for part in parts):
            score += 40
            reasons.append("contains routes")

        if any(part.lower() in _ARCH_SIGNIFICANT_DIRS for part in parts[:-1]):
            score += 30
            reasons.append("arch-significant dir")

        is_test = (
            name.startswith("test_")
            or name.endswith(("_test.py", ".spec.ts", ".spec.js", ".test.ts", ".test.js"))
            or any(t in rel_str for t in ("__tests__/", "/spec/", "/tests/"))
        )
        if is_test:
            score += 15
            reasons.append("test file")
        elif suffix in _CONFIG_EXTENSIONS or name in _CONFIG_FILENAMES:
            score += 5
            reasons.append("config file")

        reason_str = ", ".join(reasons) if reasons else "source file"

        try:
            size = file_path.stat().st_size
        except OSError:
            size = 0
        estimated_tokens = max(1, size // 4)

        return PrioritizedFile(
            path=file_path,
            priority_score=score,
            reason=reason_str,
            estimated_tokens=estimated_tokens,
            status="selected",
        ), None
