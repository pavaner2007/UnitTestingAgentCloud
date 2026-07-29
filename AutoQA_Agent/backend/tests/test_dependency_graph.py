"""
Tests for DependencyGraphAgent — file import parsing, node sizing, and cycle detection.
"""
import tempfile
from pathlib import Path

import pytest

from app.agents.dependency_graph_agent import DependencyGraphAgent


def _make_file(root: Path, rel_path: str, content: str) -> Path:
    p = root / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def test_python_import_dependencies():
    root = Path(tempfile.mkdtemp())
    f_db = _make_file(root, "app/db.py", "class DB: pass\n")
    f_models = _make_file(root, "app/models.py", "from app.db import DB\n")
    f_main = _make_file(root, "app/main.py", "from app.models import User\nfrom app.db import DB\n")

    agent = DependencyGraphAgent()
    result = agent.build_graph(root, [f_main, f_models, f_db])

    nodes = {n["file"]: n["dependency_count"] for n in result["nodes"]}
    assert nodes.get("app/db.py", 0) == 2  # main and models both import db
    assert nodes.get("app/models.py", 0) == 1
    assert result["most_depended_on"] == "app/db.py"


def test_js_relative_import_dependencies():
    root = Path(tempfile.mkdtemp())
    f_utils = _make_file(root, "src/utils.js", "export function add() {}\n")
    f_app = _make_file(root, "src/app.js", "import { add } from './utils';\n")

    agent = DependencyGraphAgent()
    result = agent.build_graph(root, [f_app, f_utils])

    nodes = {n["file"]: n["dependency_count"] for n in result["nodes"]}
    assert nodes.get("src/utils.js") == 1
    assert len(result["edges"]) == 1
    assert result["edges"][0]["from_file"] == "src/app.js"
    assert result["edges"][0]["to_file"] == "src/utils.js"


def test_cycle_detection_dfs():
    root = Path(tempfile.mkdtemp())
    # Circular dependency: a -> b -> a
    f_a = _make_file(root, "app/a.py", "from app.b import bar\n")
    f_b = _make_file(root, "app/b.py", "from app.a import foo\n")

    agent = DependencyGraphAgent()
    result = agent.build_graph(root, [f_a, f_b])

    assert len(result["cycles"]) > 0
    cycle_files = set(result["cycles"][0])
    assert "app/a.py" in cycle_files
    assert "app/b.py" in cycle_files


def test_no_cycle_in_acyclic_graph():
    root = Path(tempfile.mkdtemp())
    f_a = _make_file(root, "app/a.py", "from app.b import bar\n")
    f_b = _make_file(root, "app/b.py", "x = 1\n")

    agent = DependencyGraphAgent()
    result = agent.build_graph(root, [f_a, f_b])

    assert result["cycles"] == []
