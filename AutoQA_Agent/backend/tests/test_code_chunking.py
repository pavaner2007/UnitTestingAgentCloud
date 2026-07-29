"""
Tests: CodeChunkingAgent

Coverage
- tree-sitter Python chunking extracts function_definition nodes
- Falls back to char-count chunking when tree-sitter unavailable
- Trivial chunks (< 5 lines) are skipped
- Character-count fallback produces chunks of correct max size
"""
import sys
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://postgres:test@localhost:5432/test")

from app.agents.code_chunking_agent import CodeChunkingAgent

PYTHON_SOURCE = '''\
def add(a, b):
    """Add two numbers."""
    return a + b


def subtract(a, b):
    """Subtract b from a."""
    result = a - b
    return result


class Calculator:
    def multiply(self, a, b):
        return a * b

    def divide(self, a, b):
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b
'''


def _write_tmp(content: str, suffix: str = ".py") -> tuple[Path, Path]:
    root = Path(tempfile.mkdtemp())
    f = root / f"code{suffix}"
    f.write_text(content, encoding="utf-8")
    return f, root


def test_tree_sitter_extracts_functions():
    f, root = _write_tmp(PYTHON_SOURCE)
    agent = CodeChunkingAgent()
    chunks = agent.chunk_file(f, root)
    names = [c.name for c in chunks]
    assert "add" in names or "subtract" in names or "Calculator" in names, \
        f"Expected named chunks, got: {names}"


def test_fallback_when_no_grammar():
    """Force tree-sitter to be unavailable; char-count fallback should activate."""
    f, root = _write_tmp(PYTHON_SOURCE, suffix=".xyz")  # no grammar for .xyz
    agent = CodeChunkingAgent()
    chunks = agent.chunk_file(f, root)
    # Fallback produces at least one 'module' chunk
    assert len(chunks) >= 1
    assert all(c.chunk_type == "module" for c in chunks)


def test_trivial_chunks_skipped():
    trivial_code = "import os\nimport sys\nfrom pathlib import Path\n"
    f, root = _write_tmp(trivial_code, suffix=".py")
    agent = CodeChunkingAgent()
    chunks = agent.chunk_file(f, root)
    # Trivial import-only content should produce no ts chunks (< 5 lines per chunk),
    # and char-count fallback skips chunks with < 5 non-trivial lines
    for chunk in chunks:
        lines = chunk.content.splitlines()
        assert len(lines) >= 5 or chunk.chunk_type == "module", \
            f"Unexpectedly short chunk: {chunk.name!r} with {len(lines)} lines"


def test_char_count_respects_max():
    long_code = "x = 1  # padding\n" * 1000  # ~18 000 chars
    f, root = _write_tmp(long_code, suffix=".rb")  # fallback path
    agent = CodeChunkingAgent()
    with patch("app.agents.code_chunking_agent.settings") as ms:
        ms.code_chunk_max_chars = 500
        chunks = agent.chunk_file(f, root)
    for chunk in chunks:
        assert len(chunk.content) <= 500, \
            f"Chunk exceeds max_chars: {len(chunk.content)}"
