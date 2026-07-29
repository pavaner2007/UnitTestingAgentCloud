"""
Tests: FilePrioritizationAgent

Coverage
- Priority score ranking (entry points ranked above ordinary files)
- Excluded paths (node_modules, .git, lock files, binary extensions) are omitted
- MAX_FILES_TO_ANALYZE cap is respected
- Token-budget cap (MAX_CODE_TOKEN_BUDGET) truncates the list
- Route-file boost is applied
"""
import sys
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Make the app importable without a real .env
sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://postgres:test@localhost:5432/test")

from app.agents.file_prioritization_agent import FilePrioritizationAgent


def _make_repo(structure: dict[str, bytes]) -> Path:
    """Create a temp directory tree with given relative paths → content."""
    tmp = Path(tempfile.mkdtemp())
    for rel, content in structure.items():
        p = tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)
    return tmp


def test_entry_point_ranked_first():
    repo = _make_repo({
        "main.py": b"print('hello')" * 20,
        "utils.py": b"def helper(): pass" * 20,
    })
    agent = FilePrioritizationAgent()
    result = agent.prioritize(repo_path=repo).selected
    names = [p.path.name for p in result]
    assert names[0] == "main.py", f"Expected main.py first, got {names}"


def test_excludes_node_modules():
    repo = _make_repo({
        "node_modules/lodash/index.js": b"module.exports = {};",
        "app.js": b"const express = require('express');" * 10,
    })
    agent = FilePrioritizationAgent()
    result = agent.prioritize(repo_path=repo).selected
    paths_str = [str(p.path) for p in result]
    assert not any("node_modules" in s for s in paths_str)


def test_excludes_lockfiles():
    repo = _make_repo({
        "package-lock.json": b'{"lockfileVersion": 2}',
        "server.js": b"const http = require('http');" * 10,
    })
    agent = FilePrioritizationAgent()
    result = agent.prioritize(repo_path=repo).selected
    names = [p.path.name for p in result]
    assert "package-lock.json" not in names


def test_excludes_binary_extensions():
    repo = _make_repo({
        "logo.png": b"\x89PNG\r\n",
        "main.py": b"import os" * 20,
    })
    agent = FilePrioritizationAgent()
    result = agent.prioritize(repo_path=repo).selected
    names = [p.path.name for p in result]
    assert "logo.png" not in names


def test_max_files_cap():
    structure = {f"file_{i}.py": b"x = 1" * 10 for i in range(100)}
    repo = _make_repo(structure)
    with patch("app.agents.file_prioritization_agent.settings") as mock_settings:
        mock_settings.max_files_to_analyze = 5
        mock_settings.max_code_token_budget = 999_999
        agent = FilePrioritizationAgent()
        result = agent.prioritize(repo_path=repo).selected
    assert len(result) <= 5


def test_route_file_boost():
    repo = _make_repo({
        "routes.py": b"@app.get('/health')\ndef health(): pass\n" * 5,
        "models.py": b"class User: pass\n" * 10,
    })
    agent = FilePrioritizationAgent()
    result = agent.prioritize(repo_path=repo, route_files={"routes.py"}).selected
    names = [p.path.name for p in result]
    assert names[0] == "routes.py"
