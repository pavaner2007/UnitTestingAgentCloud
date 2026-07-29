"""
PatternDetector — deterministic, regex-based scanner that identifies notable
code patterns across a repository's source files and chunks.

This detector is intentionally NOT an LLM — it is pure Python regex, which
means results are cheap, reproducible, and unit-testable.

Pattern categories (all deterministic — no LLM):
  - Auth            : JWT, OAuth, login-required decorators
  - Raw SQL         : cursor.execute / string-formatted SQL
  - External API    : requests, httpx, fetch, axios
  - Env / secrets   : os.environ, process.env, dotenv
  - Subprocess/exec : subprocess., os.system, exec(), eval()
  - File I/O        : open(), fs.readFile, fs.writeFile
  - Hardcoded secret: API-key-shaped literals assigned to variables (HIGH severity)
  - TODO/FIXME      : developer comments flagging incomplete/hacky code

Debug mode: set PATTERN_DETECTOR_DEBUG=true in environment to log per-file
match/miss details for each category. Useful to verify the detector is
actually scanning real repo content, not silently failing.

Output: List[str] — human-readable descriptions with file context,
  e.g. "JWT auth in backend/app/api/routes.py"
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# Read debug flag once at import time (can override per-test via env)
_DEBUG = os.environ.get("PATTERN_DETECTOR_DEBUG", "").lower() in ("1", "true", "yes")


# ── Pattern definitions ────────────────────────────────────────────────────────

@dataclass
class _PatternRule:
    label: str          # human-readable category label
    patterns: list[re.Pattern]
    severity: str = "info"  # "high" | "medium" | "info"


_RULES: list[_PatternRule] = [
    _PatternRule(
        label="JWT auth",
        patterns=[
            re.compile(r"jwt\.decode", re.IGNORECASE),
            re.compile(r"verify_token", re.IGNORECASE),
            re.compile(r"Depends\s*\(\s*oauth2_scheme", re.IGNORECASE),
            re.compile(r"@jwt_required", re.IGNORECASE),
            re.compile(r"@login_required", re.IGNORECASE),
            re.compile(r"Bearer\s+", re.IGNORECASE),
        ],
    ),
    _PatternRule(
        label="Raw SQL",
        severity="medium",
        patterns=[
            re.compile(r"cursor\.execute\s*\(", re.IGNORECASE),
            re.compile(r"\.execute\s*\(\s*[\"']SELECT", re.IGNORECASE),
            re.compile(r"\.execute\s*\(\s*[\"']INSERT", re.IGNORECASE),
            re.compile(r"\.execute\s*\(\s*[\"']UPDATE", re.IGNORECASE),
            re.compile(r"\.execute\s*\(\s*[\"']DELETE", re.IGNORECASE),
            # f-string / %-formatted SQL — a SQL injection risk marker
            re.compile(r"f[\"']SELECT.*\{", re.IGNORECASE),
            re.compile(r"f[\"']INSERT.*\{", re.IGNORECASE),
        ],
    ),
    _PatternRule(
        label="External API call",
        patterns=[
            re.compile(r"requests\.(get|post|put|patch|delete|request)\s*\(", re.IGNORECASE),
            re.compile(r"httpx\.(get|post|put|patch|delete|request|AsyncClient)\s*[\(.]", re.IGNORECASE),
            re.compile(r"\bfetch\s*\(", re.IGNORECASE),
            re.compile(r"\baxios\.(get|post|put|patch|delete|request)\s*\(", re.IGNORECASE),
        ],
    ),
    _PatternRule(
        label="Env/secrets usage",
        patterns=[
            re.compile(r"os\.environ", re.IGNORECASE),
            re.compile(r"os\.getenv\s*\(", re.IGNORECASE),
            re.compile(r"process\.env\.", re.IGNORECASE),
            re.compile(r"\bload_dotenv\s*\(", re.IGNORECASE),
            re.compile(r"dotenv\.config\s*\(", re.IGNORECASE),
        ],
    ),
    # ── NEW CATEGORIES ────────────────────────────────────────────────────────
    _PatternRule(
        label="Subprocess/system call",
        severity="medium",
        patterns=[
            re.compile(r"\bsubprocess\.", re.IGNORECASE),
            re.compile(r"\bos\.system\s*\(", re.IGNORECASE),
            re.compile(r"\bexec\s*\(", re.IGNORECASE),
            re.compile(r"\beval\s*\(", re.IGNORECASE),
        ],
    ),
    _PatternRule(
        label="File I/O",
        patterns=[
            re.compile(r"\bopen\s*\(", re.IGNORECASE),
            re.compile(r"\bwith\s+open\s*\(", re.IGNORECASE),
            re.compile(r"\bfs\.readFile\b", re.IGNORECASE),
            re.compile(r"\bfs\.writeFile\b", re.IGNORECASE),
            re.compile(r"\bfs\.promises\.", re.IGNORECASE),
        ],
    ),
    _PatternRule(
        label="Hardcoded secret",
        severity="high",
        patterns=[
            # API key / token literals: api_key = "sk-..." or API_KEY = "..."
            re.compile(r'(?:api[_-]?key|api[_-]?secret|access[_-]?token|secret[_-]?key|auth[_-]?token|private[_-]?key)\s*=\s*["\'][^"\']{8,}["\']', re.IGNORECASE),
            # Password literals: password = "something"
            re.compile(r'\bpassword\s*=\s*["\'][^"\']{4,}["\']', re.IGNORECASE),
            # OpenAI / Anthropic / common key prefixes
            re.compile(r'["\']sk-[A-Za-z0-9]{20,}["\']'),
            re.compile(r'["\']ghp_[A-Za-z0-9]{36}["\']'),
        ],
    ),
    _PatternRule(
        label="TODO/FIXME comment",
        patterns=[
            re.compile(r"#\s*(TODO|FIXME|HACK|XXX)\b", re.IGNORECASE),
            re.compile(r"//\s*(TODO|FIXME|HACK|XXX)\b", re.IGNORECASE),
            re.compile(r"/\*\s*(TODO|FIXME|HACK|XXX)\b", re.IGNORECASE),
        ],
    ),
]

# File extensions we'll scan (skip binary/non-text)
_SCANNABLE_EXTENSIONS = frozenset({
    ".py", ".js", ".jsx", ".ts", ".tsx",
    ".go", ".java", ".rb", ".rs", ".c", ".cpp", ".h",
    ".cs", ".php", ".swift", ".kt",
})


# ── Detector ──────────────────────────────────────────────────────────────────

class PatternDetector:
    """Scan source files/chunks for notable code patterns."""

    def detect_in_files(
        self,
        file_paths: list[Path],
        repo_root: Path,
    ) -> list[str]:
        """
        Scan a list of file paths and return de-duplicated pattern strings.

        When PATTERN_DETECTOR_DEBUG=true, logs per-file match/miss details
        for each category so detection can be verified on real repo content.
        """
        findings: dict[str, set[str]] = {}   # label → set of file rel-paths

        for file_path in file_paths:
            if file_path.suffix.lower() not in _SCANNABLE_EXTENSIONS:
                if _DEBUG:
                    logger.debug("PatternDetector [SKIP-EXT] %s", file_path.name)
                continue
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            try:
                rel = str(file_path.relative_to(repo_root))
            except ValueError:
                rel = file_path.name

            if _DEBUG:
                logger.debug("PatternDetector scanning %s (%d chars)", rel, len(content))

            for rule in _RULES:
                matched = any(pattern.search(content) for pattern in rule.patterns)
                if _DEBUG:
                    logger.debug(
                        "  [%s] %s → %s",
                        "MATCH" if matched else "miss ",
                        rule.label, rel,
                    )
                if matched:
                    findings.setdefault(rule.label, set()).add(rel)

        # Format as human-readable strings
        result: list[str] = []
        for label, paths in sorted(findings.items()):
            for p in sorted(paths):
                result.append(f"{label} in {p}")

        logger.info("PatternDetector: %d notable pattern(s) found", len(result))
        return result

    def detect_in_chunks(self, chunks: list) -> list[str]:
        """
        Convenience method: scan a list of CodeChunk objects.
        Returns de-duplicated pattern strings with file+name context.
        """
        findings: dict[str, set[str]] = {}

        for chunk in chunks:
            for rule in _RULES:
                if any(pattern.search(chunk.content) for pattern in rule.patterns):
                    label_key = rule.label
                    context = f"{chunk.file_path} ({chunk.name})"
                    findings.setdefault(label_key, set()).add(context)

        result: list[str] = []
        for label, contexts in sorted(findings.items()):
            for ctx in sorted(contexts):
                result.append(f"{label} in {ctx}")

        return result
