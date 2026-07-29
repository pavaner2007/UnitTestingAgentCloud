"""
CodeChunkingAgent — splits source files into semantic chunks (functions / classes)
using tree-sitter grammars, falling back to character-count chunking when no
grammar is available for the language.

Supported grammars (via tree-sitter-languages)
-----------------------------------------------
Python, JavaScript, TypeScript, Go, Java, C, C++, Ruby, Rust

Fallback
--------
Any file whose extension has no registered grammar is chunked by character
count (settings.code_chunk_max_chars) — the same logic that existed before.
Trivial chunks (< 5 lines, pure imports) are skipped.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Data class ────────────────────────────────────────────────────────────────

@dataclass
class CodeChunk:
    file_path: str          # repo-relative path string
    chunk_type: str         # 'function' | 'class' | 'module' (fallback)
    name: str               # identifier name, or basename for module chunks
    content: str            # source text of the chunk
    start_line: int
    end_line: int


# ── Grammar map: file extension → tree-sitter language name ──────────────────

_EXT_TO_LANG: dict[str, str] = {
    ".py":  "python",
    ".js":  "javascript",
    ".jsx": "javascript",
    ".ts":  "typescript",
    ".tsx": "tsx",
    ".go":  "go",
    ".java":"java",
    ".c":   "c",
    ".h":   "c",
    ".cpp": "cpp",
    ".cc":  "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".rb":  "ruby",
    ".rs":  "rust",
}

# tree-sitter node types that represent a named callable/class block
_CHUNK_NODE_TYPES: dict[str, set[str]] = {
    "python":     {"function_definition", "class_definition"},
    "javascript": {"function_declaration", "function_expression", "arrow_function",
                   "class_declaration", "method_definition"},
    "typescript": {"function_declaration", "function_expression", "arrow_function",
                   "class_declaration", "method_definition"},
    "tsx":        {"function_declaration", "function_expression", "arrow_function",
                   "class_declaration", "method_definition"},
    "go":         {"function_declaration", "method_declaration"},
    "java":       {"method_declaration", "class_declaration", "constructor_declaration"},
    "c":          {"function_definition"},
    "cpp":        {"function_definition", "class_specifier"},
    "ruby":       {"method", "class"},
    "rust":       {"function_item", "impl_item"},
}

_TRIVIAL_PYTHON_PATTERNS = ("import ", "from ", "#", "@")


# ── Agent ─────────────────────────────────────────────────────────────────────

class CodeChunkingAgent:
    """Parse source files into semantic chunks, with char-count fallback."""

    def __init__(self) -> None:
        self._parsers: dict[str, Any] = {}   # lang → Parser (lazy init)
        self._ts_available = self._check_ts()

    # ── Public ────────────────────────────────────────────────────────────────

    def chunk_file(self, file_path: Path, repo_root: Path) -> list[CodeChunk]:
        """Return semantic chunks for a single source file."""
        try:
            rel = str(file_path.relative_to(repo_root))
        except ValueError:
            rel = file_path.name

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            logger.debug("Cannot read %s: %s", file_path, exc)
            return []

        if not content.strip():
            return []

        suffix = file_path.suffix.lower()
        lang = _EXT_TO_LANG.get(suffix)

        if lang and self._ts_available:
            chunks = self._ts_chunk(content, lang, rel)
            if chunks:
                return chunks
            # Tree-sitter parsed but found no named top-level items → fall back
            logger.debug("tree-sitter found no chunks for %s, using char fallback", rel)

        return self._char_chunk(content, rel)

    # ── tree-sitter path ──────────────────────────────────────────────────────

    def _check_ts(self) -> bool:
        try:
            import tree_sitter_languages  # noqa: F401
            return True
        except ImportError:
            logger.warning("tree-sitter-languages not installed — using char fallback for all files")
            return False

    def _get_parser(self, lang: str) -> Any:
        """Return a pre-configured tree-sitter Parser for the given language.

        Uses tree_sitter_languages.get_parser() which is the recommended API for
        tree-sitter-languages 1.10.x + tree-sitter 0.21.x.
        """
        if lang in self._parsers:
            return self._parsers[lang]
        try:
            from tree_sitter_languages import get_parser as tsl_get_parser
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", FutureWarning)
                parser = tsl_get_parser(lang)
            self._parsers[lang] = parser
            return parser
        except Exception as exc:
            logger.debug("No tree-sitter grammar for '%s': %s", lang, exc)
            self._parsers[lang] = None
            return None

    def _ts_chunk(self, content: str, lang: str, rel_path: str) -> list[CodeChunk]:
        parser = self._get_parser(lang)
        if parser is None:
            return []

        try:
            tree = parser.parse(content.encode("utf-8", errors="replace"))
        except Exception as exc:
            logger.debug("tree-sitter parse failed for %s: %s", rel_path, exc)
            return []

        target_types = _CHUNK_NODE_TYPES.get(lang, set())
        chunks: list[CodeChunk] = []

        def _name_of(node) -> str:
            """Extract identifier name from a tree-sitter node.

            Tries the 'name' field first (tree-sitter 0.20+ field API), then
            walks children looking for an identifier/name type node.
            """
            # tree-sitter 0.20+: most grammar nodes expose a 'name' field
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                raw = name_node.text
                if raw:
                    return raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
            # Fallback: scan immediate children for identifier/name types
            for child in node.children:
                if child.type in ("identifier", "name", "type_identifier"):
                    raw = child.text
                    if raw:
                        return raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
            return "unknown"

        def _walk(node) -> None:
            if node.type in target_types:
                start = node.start_point[0]   # 0-indexed row
                end   = node.end_point[0]
                n_lines = end - start + 1

                if n_lines < 6:
                    # Too trivial — skip
                    return

                chunk_content = content[node.start_byte:node.end_byte]
                if len(chunk_content) > settings.code_chunk_max_chars:
                    chunk_content = chunk_content[:settings.code_chunk_max_chars]

                chunk_type = "class" if "class" in node.type else "function"
                chunks.append(CodeChunk(
                    file_path=rel_path,
                    chunk_type=chunk_type,
                    name=_name_of(node),
                    content=chunk_content,
                    start_line=start + 1,
                    end_line=end + 1,
                ))
                # Don't recurse into this node — top-level only
                return

            for child in node.children:
                _walk(child)

        _walk(tree.root_node)
        return chunks

    # ── Character-count fallback path ─────────────────────────────────────────

    def _char_chunk(self, content: str, rel_path: str) -> list[CodeChunk]:
        """Split content by max_chars, skipping near-empty or import-only chunks."""
        max_chars = settings.code_chunk_max_chars
        chunks: list[CodeChunk] = []
        start = 0
        chunk_idx = 0

        while start < len(content):
            end = min(start + max_chars, len(content))
            slice_text = content[start:end]

            lines = slice_text.splitlines()
            non_trivial = [
                l for l in lines
                if l.strip() and not any(l.strip().startswith(p) for p in _TRIVIAL_PYTHON_PATTERNS)
            ]
            if len(non_trivial) >= 5:
                start_line = content[:start].count("\n") + 1
                end_line   = content[:end].count("\n") + 1
                chunks.append(CodeChunk(
                    file_path=rel_path,
                    chunk_type="module",
                    name=f"chunk_{chunk_idx}",
                    content=slice_text,
                    start_line=start_line,
                    end_line=end_line,
                ))
                chunk_idx += 1

            start = end

        return chunks
