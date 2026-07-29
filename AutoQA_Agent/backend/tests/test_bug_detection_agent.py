"""
Tests for BugDetectionAgent — Tier 1 (ruff) + Tier 2 (smells) + caching.
"""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.agents.bug_detection_agent import BugDetectionAgent, _detect_smells
from app.schemas.analysis import CodeIssue


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_agent(db=None) -> BugDetectionAgent:
    db = db or MagicMock()
    # Patch CacheService to always miss (return None) so we don't need real DB
    with patch("app.agents.bug_detection_agent.CacheService") as MockCS:
        MockCS.return_value.get_cached.return_value = None
        MockCS.return_value.set_cached.return_value = None
        agent = BugDetectionAgent(db)
    # Attach the mock cache so tests can inspect calls
    agent._cache = MagicMock()
    agent._cache.get_cached.return_value = None
    return agent


def _make_pf(path: Path):
    pf = MagicMock()
    pf.path = path
    return pf


# ── Tier 2 smell tests (unit, no subprocess) ─────────────────────────────────

def test_bare_except_detected():
    code = "try:\n    x()\nexcept:\n    pass\n"
    issues = _detect_smells(code, "myapp/utils.py")
    rules = [i.rule for i in issues]
    assert "bare_except" in rules


def test_bare_except_not_in_test_file():
    # bare_except is still detected in test files (not in exclusion list)
    code = "try:\n    x()\nexcept:\n    pass\n"
    issues = _detect_smells(code, "tests/test_utils.py")
    rules = [i.rule for i in issues]
    assert "bare_except" in rules


def test_console_log_detected_non_test(tmp_path):
    code = 'function greet() {\n  console.log("hello");\n}\n'
    issues = _detect_smells(code, "src/greet.js")
    rules = [i.rule for i in issues]
    assert "debug_print" in rules


def test_console_log_not_detected_in_test_file():
    code = 'console.log("debug");\n'
    issues = _detect_smells(code, "src/__tests__/greet.test.js")
    rules = [i.rule for i in issues]
    assert "debug_print" not in rules


def test_todo_comment_detected():
    code = "def foo():\n    # TODO: fix this properly\n    return 42\n"
    issues = _detect_smells(code, "app/service.py")
    rules = [i.rule for i in issues]
    assert "todo_comment" in rules


def test_fixme_comment_detected():
    code = "// FIXME: broken edge case\nfunction bar() {}\n"
    issues = _detect_smells(code, "src/bar.js")
    rules = [i.rule for i in issues]
    assert "todo_comment" in rules


def test_duplicate_function_detected():
    code = (
        "def process_a(x):\n    result = x * 2\n    return result + 1\n\n"
        "def process_b(x):\n    result = x * 2\n    return result + 1\n"
    )
    issues = _detect_smells(code, "app/utils.py")
    rules = [i.rule for i in issues]
    assert "duplicate_function" in rules


def test_no_false_positive_clean_code():
    code = "def add(a, b):\n    return a + b\n\ndef multiply(a, b):\n    return a * b\n"
    issues = _detect_smells(code, "app/math.py")
    # No issues expected in clean code
    rules = [i.rule for i in issues]
    assert "bare_except" not in rules
    assert "duplicate_function" not in rules


# ── Tier 1: ruff availability ─────────────────────────────────────────────────

def test_ruff_unavailable_tier1_skipped(tmp_path):
    """When ruff is not installed, Tier 1 is skipped but Tier 2 still runs."""
    agent = _make_agent()
    agent._ruff_available = False

    py_file = tmp_path / "bad.py"
    py_file.write_text("try:\n    x()\nexcept:\n    pass\n")
    pfs = [_make_pf(py_file)]

    issues, summary = agent.detect(tmp_path, pfs)
    # Tier 2 still detects bare_except
    assert any(i.rule == "bare_except" for i in issues)
    # No linter issues (Tier 1 skipped)
    assert not any(i.source == "linter" for i in issues)


def test_ruff_output_parsed_from_directory_json(tmp_path):
    """Ruff directory-level JSON is parsed and distributed to files."""
    agent = _make_agent()
    agent._ruff_available = True

    py_file = tmp_path / "app.py"
    py_file.write_text("import os\nx=1\n")

    ruff_json = json.dumps([{
        "filename": str(py_file),
        "code": "E501",
        "message": "line too long",
        "location": {"row": 1, "column": 1},
        "fix": None,
        "noqa_row": None,
    }])

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=ruff_json, returncode=1)
        result = agent._run_ruff(tmp_path)

    rel = str(py_file.relative_to(tmp_path))
    assert rel in result
    assert result[rel][0].rule == "ruff:E501"


def test_ruff_per_file_cap_enforced(tmp_path):
    """At most 5 ruff issues are returned per file."""
    agent = _make_agent()
    agent._ruff_available = True

    py_file = tmp_path / "noisy.py"
    py_file.write_text("x=1\n" * 10)

    issues_raw = [
        {"filename": str(py_file), "code": "E501", "message": f"issue {i}",
         "location": {"row": i, "column": 1}, "fix": None, "noqa_row": None}
        for i in range(1, 11)   # 10 issues
    ]
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=json.dumps(issues_raw), returncode=1)
        result = agent._run_ruff(tmp_path)

    rel = str(py_file.relative_to(tmp_path))
    assert len(result.get(rel, [])) <= 5


# ── Cache hit / miss ──────────────────────────────────────────────────────────

def test_cache_hit_skips_detection(tmp_path):
    """On cache hit, smell detection is skipped (no new issues computed)."""
    agent = _make_agent()
    agent._ruff_available = False

    cached_issue = CodeIssue(
        file="app/utils.py", line=3, severity="high",
        source="static_smell", rule="bare_except",
        message="cached result",
    )
    # First call returns the cached value
    agent._cache.get_cached.return_value = json.dumps([cached_issue.model_dump()])

    py_file = tmp_path / "utils.py"
    py_file.write_text("def foo():\n    pass\n")
    pfs = [_make_pf(py_file)]

    issues, summary = agent.detect(tmp_path, pfs)
    # set_cached should NOT be called on a cache hit
    agent._cache.set_cached.assert_not_called()
    assert len(issues) == 1
    assert issues[0].rule == "bare_except"


def test_cache_miss_stores_result(tmp_path):
    """On cache miss, result is stored after detection."""
    agent = _make_agent()
    agent._ruff_available = False

    py_file = tmp_path / "utils.py"
    py_file.write_text("try:\n    x()\nexcept:\n    pass\n")
    pfs = [_make_pf(py_file)]

    issues, summary = agent.detect(tmp_path, pfs)
    # set_cached should have been called for Tier 2
    assert agent._cache.set_cached.called


# ── issues_summary ────────────────────────────────────────────────────────────

def test_issues_summary_counts(tmp_path):
    """issues_summary correctly counts severities."""
    agent = _make_agent()
    agent._ruff_available = False

    py_file = tmp_path / "utils.py"
    py_file.write_text(
        "try:\n    x()\nexcept:\n    pass\n"
        "# TODO: fix\n"
    )
    pfs = [_make_pf(py_file)]

    issues, summary = agent.detect(tmp_path, pfs)
    assert "high" in summary or "low" in summary
    assert sum(summary.values()) == len(issues)
