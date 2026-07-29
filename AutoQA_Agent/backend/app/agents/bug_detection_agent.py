"""
BugDetectionAgent — deterministic code-quality and bug detection with suggestions.

Two tiers of detection (no LLM, pure static analysis):

Tier 1 — ruff (Python only, optional)
--------------------------------------
  - Checks shutil.which("ruff") at instantiation; logs warning and skips if absent.
  - Runs `ruff check --output-format=json <repo_root>` ONCE per analysis.
  - Generates suggestions from ruff rule codes, fix presence, and prose messages.
  - Capped at 5 issues per file (highest severity first).

Tier 2 — Deterministic smells (all scannable languages)
---------------------------------------------------------
  - Bare except:  bare `except:` or `except Exception:`
  - Pass-only:    function/method body that is only `pass`
  - Deep nesting: >4 levels of if/else/for/while indentation
  - Print/log:    print() or console.log() in non-test files
  - TODO/FIXME:   # TODO / # FIXME / # HACK comments
  - Duplicate fn: near-duplicate function bodies (Jaccard ≥ 0.85, same file)
"""
from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.schemas.analysis import CodeIssue
from app.services.cache_service import CacheService, sha256_of

logger = logging.getLogger(__name__)

_SCANNABLE = frozenset({
    ".py", ".js", ".jsx", ".ts", ".tsx",
    ".go", ".java", ".rb", ".rs",
})
_PY = frozenset({".py"})

_SMELL_CACHE_KEY  = "static_smell_v2"
_RUFF_CACHE_KEY   = "ruff_v2"
_SUMMARY_TYPE     = "bug_issues"

_RUFF_FILE_CAP = 5

_RUFF_SEVERITY_HIGH   = frozenset({"E", "F"})   # errors
_RUFF_SEVERITY_MEDIUM = frozenset({"W", "C", "N", "B"})  # warnings/convention


def _ruff_severity(code: str) -> str:
    prefix = code[0].upper() if code else "W"
    if prefix in _RUFF_SEVERITY_HIGH:
        return "high"
    if prefix in _RUFF_SEVERITY_MEDIUM:
        return "medium"
    return "low"


# Static lookup table for common ruff rule codes
_RUFF_SUGGESTIONS: dict[str, str] = {
    "E722": "Do not use bare 'except'; specify explicit exception type (e.g. ValueError).",
    "F401": "Remove unused import or add to __all__ export list.",
    "F841": "Remove unused local variable or prefix variable name with underscore.",
    "E501": "Wrap line or break expressions to comply with 88/100 char line limit.",
    "F403": "Replace wildcard 'from module import *' with explicit symbol imports.",
    "E402": "Move module import statement to top of file.",
    "F811": "Remove or rename re-definition of function/variable in scope.",
    "B008": "Do not perform function call in argument default; use None indicator.",
    "F821": "Define or import the undefined name before usage.",
}

_SMELL_SUGGESTIONS: dict[str, str] = {
    "bare_except": "Catch a specific exception type (e.g. ValueError) and log or re-raise it.",
    "pass_only_body": "Implement the function logic or raise NotImplementedError.",
    "deep_nesting": "Refactor deeply nested conditional/loop (>4 levels) into smaller helper functions.",
    "debug_print": "Replace print/console.log statement with a structured logger call.",
    "todo_comment": "Resolve TODO/FIXME comment before pushing code to production.",
    "duplicate_function": "Extract duplicate function logic into a common shared helper function.",
}

# ── Smell patterns ────────────────────────────────────────────────────────────

_RE_BARE_EXCEPT = re.compile(r"^\s*except\s*(?:Exception\s*)?:\s*$", re.MULTILINE)
_RE_PASS_ONLY   = re.compile(
    r"^\s*def\s+\w+[^:]*:\s*\n(\s+)pass\s*$",
    re.MULTILINE,
)
_RE_PRINT_PY    = re.compile(r"\bprint\s*\(", re.IGNORECASE)
_RE_CONSOLE_LOG = re.compile(r"\bconsole\s*\.\s*log\s*\(", re.IGNORECASE)
_RE_TODO        = re.compile(r"(?:#|//)\s*(TODO|FIXME|HACK)\b", re.IGNORECASE)


def _is_test_file(path: str) -> bool:
    return any(t in path for t in ("test_", "_test.", ".spec.", ".test.", "__tests__", "/tests/"))


def _jaccard(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union else 0.0


def _detect_smells(content: str, rel_path: str) -> list[CodeIssue]:
    """Run Tier 2 smell detection on a single file's content."""
    issues: list[CodeIssue] = []
    lines = content.splitlines()
    suffix = rel_path.rsplit(".", 1)[-1] if "." in rel_path else ""
    is_test = _is_test_file(rel_path)
    is_py = suffix == "py"

    # ── Bare except ───────────────────────────────────────────────────────────
    for i, line in enumerate(lines, 1):
        if _RE_BARE_EXCEPT.match(line):
            issues.append(CodeIssue(
                file=rel_path, line=i, severity="high",
                source="static_smell", rule="bare_except",
                message="Bare `except:` or `except Exception:` — catches all errors silently",
                suggestion=_SMELL_SUGGESTIONS["bare_except"],
            ))

    # ── pass-only function bodies ─────────────────────────────────────────────
    if is_py:
        for m in _RE_PASS_ONLY.finditer(content):
            lineno = content[:m.start()].count("\n") + 1
            issues.append(CodeIssue(
                file=rel_path, line=lineno, severity="low",
                source="static_smell", rule="pass_only_body",
                message="Function body contains only `pass` — stub or unimplemented",
                suggestion=_SMELL_SUGGESTIONS["pass_only_body"],
            ))

    # ── Deep nesting ─────────────────────────────────────────────────────────
    _nest_re = re.compile(r"^( {20,}|\t{5,})(if|else|elif|for|while|try|with)\b")
    for i, line in enumerate(lines, 1):
        if _nest_re.match(line):
            issues.append(CodeIssue(
                file=rel_path, line=i, severity="medium",
                source="static_smell", rule="deep_nesting",
                message="Deeply nested conditional/loop (>4 levels) — consider refactoring",
                suggestion=_SMELL_SUGGESTIONS["deep_nesting"],
            ))
            break

    # ── print / console.log in non-test files ─────────────────────────────────
    if not is_test:
        pattern = _RE_PRINT_PY if is_py else _RE_CONSOLE_LOG
        for i, line in enumerate(lines, 1):
            if pattern.search(line):
                issues.append(CodeIssue(
                    file=rel_path, line=i, severity="low",
                    source="static_smell", rule="debug_print",
                    message="Leftover print/console.log statement in non-test file",
                    suggestion=_SMELL_SUGGESTIONS["debug_print"],
                ))
                break

    # ── TODO/FIXME/HACK comments ──────────────────────────────────────────────
    for i, line in enumerate(lines, 1):
        m = _RE_TODO.search(line)
        if m:
            issues.append(CodeIssue(
                file=rel_path, line=i, severity="low",
                source="static_smell", rule="todo_comment",
                message=f"{m.group(1).upper()} comment — unfinished or hacky code",
                suggestion=_SMELL_SUGGESTIONS["todo_comment"],
            ))
            break

    # ── Near-duplicate functions ──────────────────────────────────────────────
    fn_re = re.compile(r"(?:^|\n)\s*(?:def|function)\s+(\w+)[^\n]*\n((?:[ \t]+[^\n]*\n?)+)", re.MULTILINE)
    functions: list[tuple[str, list[str]]] = []
    for m in fn_re.finditer(content):
        body_tokens = m.group(2).split()
        functions.append((m.group(1), body_tokens))

    for i, (name_a, toks_a) in enumerate(functions):
        for name_b, toks_b in functions[i + 1:]:
            if name_a != name_b and _jaccard(toks_a, toks_b) >= 0.85:
                issues.append(CodeIssue(
                    file=rel_path, line=None, severity="low",
                    source="static_smell", rule="duplicate_function",
                    message=f"Functions `{name_a}` and `{name_b}` have near-identical bodies (Jaccard ≥ 0.85)",
                    suggestion=_SMELL_SUGGESTIONS["duplicate_function"],
                ))
                break

    return issues


class BugDetectionAgent:
    """Run Tier 1 (ruff) + Tier 2 (smell) bug detection against prioritized files."""

    def __init__(self, db: Session) -> None:
        self._cache = CacheService(db)
        self._ruff_available = bool(shutil.which("ruff"))
        if not self._ruff_available:
            logger.warning("BugDetectionAgent: `ruff` not found in PATH — Tier 1 disabled.")
        else:
            logger.info("BugDetectionAgent: ruff available at %s", shutil.which("ruff"))

    def detect(
        self,
        repo_path: Path,
        prioritized_files: list,
    ) -> tuple[list[CodeIssue], dict[str, int]]:
        all_issues: list[CodeIssue] = []

        ruff_by_file: dict[str, list[CodeIssue]] = {}
        if self._ruff_available:
            ruff_by_file = self._run_ruff(repo_path)

        for pf in prioritized_files:
            try:
                content = pf.path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            try:
                rel = str(pf.path.relative_to(repo_path))
            except ValueError:
                rel = pf.path.name

            suffix = pf.path.suffix.lower()
            if suffix not in _SCANNABLE:
                continue

            file_issues: list[CodeIssue] = []

            if suffix in _PY and self._ruff_available:
                cache_hit = self._cache_get(content, _RUFF_CACHE_KEY)
                if cache_hit is not None:
                    file_issues.extend(cache_hit)
                else:
                    t1 = ruff_by_file.get(rel, [])
                    self._cache_set(content, _RUFF_CACHE_KEY, t1)
                    file_issues.extend(t1)

            cache_hit_t2 = self._cache_get(content, _SMELL_CACHE_KEY)
            if cache_hit_t2 is not None:
                file_issues.extend(cache_hit_t2)
            else:
                t2 = _detect_smells(content, rel)
                self._cache_set(content, _SMELL_CACHE_KEY, t2)
                file_issues.extend(t2)

            all_issues.extend(file_issues)

        issues_summary = dict(Counter(i.severity for i in all_issues))
        logger.info("BugDetectionAgent: %d issue(s) found — %s", len(all_issues), issues_summary)
        return all_issues, issues_summary

    def _run_ruff(self, repo_path: Path) -> dict[str, list[CodeIssue]]:
        by_file: dict[str, list[CodeIssue]] = {}
        try:
            result = subprocess.run(
                ["ruff", "check", "--output-format=json", str(repo_path)],
                capture_output=True, text=True, timeout=60,
            )
            raw = result.stdout.strip()
            if not raw:
                return by_file
            data: list[dict] = json.loads(raw)
        except Exception as exc:
            logger.warning("BugDetectionAgent: ruff failed — %s", exc)
            return by_file

        for item in data:
            try:
                abs_path = item.get("filename", "")
                try:
                    rel = str(Path(abs_path).relative_to(repo_path))
                except ValueError:
                    rel = abs_path

                code = item.get("code", "W000")
                sev = _ruff_severity(code)
                msg = item.get("message", "")

                base_sugg = _RUFF_SUGGESTIONS.get(code)
                if not base_sugg:
                    base_sugg = f"Address {msg.lower()}." if msg else "Review code style."

                is_autofix = bool(item.get("fix"))
                suggestion = f"Auto-fixable by ruff: {base_sugg}" if is_autofix else base_sugg

                issue = CodeIssue(
                    file=rel,
                    line=item.get("location", {}).get("row"),
                    severity=sev,
                    source="linter",
                    rule=f"ruff:{code}",
                    message=msg,
                    suggestion=suggestion,
                )
                by_file.setdefault(rel, []).append(issue)
            except Exception:
                continue

        _sev_order = {"high": 0, "medium": 1, "low": 2}
        for rel in by_file:
            by_file[rel].sort(key=lambda i: _sev_order.get(i.severity, 3))
            by_file[rel] = by_file[rel][:_RUFF_FILE_CAP]

        return by_file

    def _cache_get(self, content: str, model_key: str) -> list[CodeIssue] | None:
        h = sha256_of(content)
        raw = self._cache.get_cached(h, _SUMMARY_TYPE, model_key)
        if raw is None:
            return None
        try:
            data = json.loads(raw)
            return [CodeIssue(**item) for item in data]
        except Exception:
            return None

    def _cache_set(self, content: str, model_key: str, issues: list[CodeIssue]) -> None:
        h = sha256_of(content)
        serialized = json.dumps([i.model_dump() for i in issues], ensure_ascii=False)
        self._cache.set_cached(h, _SUMMARY_TYPE, serialized, model_key)
