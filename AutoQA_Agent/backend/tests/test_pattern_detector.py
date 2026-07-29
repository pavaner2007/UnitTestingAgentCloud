"""
Tests: PatternDetector

Coverage
- Auth patterns: JWT decode, login_required, Depends(oauth2_scheme)
- Raw SQL patterns: cursor.execute, f-string SQL
- External API patterns: requests.get, httpx.post, fetch(, axios.get
- Env/secrets patterns: os.environ, os.getenv, process.env, load_dotenv
- No false positives on unrelated source code
- File-level and chunk-level detection both work
"""
import sys
import os
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://postgres:test@localhost:5432/test")

from app.agents.pattern_detector import PatternDetector
from app.agents.code_chunking_agent import CodeChunk


def _make_file(content: str, suffix: str = ".py") -> tuple[Path, Path]:
    root = Path(tempfile.mkdtemp())
    f = root / f"source{suffix}"
    f.write_text(content, encoding="utf-8")
    return f, root


def _detect(content: str, suffix: str = ".py") -> list[str]:
    f, root = _make_file(content, suffix)
    detector = PatternDetector()
    return detector.detect_in_files([f], repo_root=root)


# ── Auth ─────────────────────────────────────────────────────────────────────

def test_detects_jwt_decode():
    results = _detect("token = jwt.decode(raw, SECRET)")
    assert any("JWT auth" in r for r in results)


def test_detects_login_required():
    results = _detect("@login_required\ndef view(): pass")
    assert any("JWT auth" in r for r in results)


def test_detects_oauth2_depends():
    results = _detect("def endpoint(user=Depends(oauth2_scheme)): pass")
    assert any("JWT auth" in r for r in results)


# ── Raw SQL ───────────────────────────────────────────────────────────────────

def test_detects_cursor_execute():
    results = _detect('cursor.execute("SELECT * FROM users WHERE id=%s", [uid])')
    assert any("Raw SQL" in r for r in results)


def test_detects_fstring_sql():
    results = _detect('db.execute(f"SELECT * FROM {table}")')
    assert any("Raw SQL" in r for r in results)


# ── External API calls ────────────────────────────────────────────────────────

def test_detects_requests_get():
    results = _detect("resp = requests.get(url, headers=headers)")
    assert any("External API" in r for r in results)


def test_detects_httpx_post():
    results = _detect("async with httpx.AsyncClient() as client: pass")
    assert any("External API" in r for r in results)


def test_detects_fetch_js(tmp_path):
    f = tmp_path / "main.js"
    f.write_text("const data = await fetch('/api/data');")
    detector = PatternDetector()
    results = detector.detect_in_files([f], repo_root=tmp_path)
    assert any("External API" in r for r in results)


def test_detects_axios(tmp_path):
    f = tmp_path / "app.js"
    f.write_text("axios.get('/api/users').then(r => r.data)")
    detector = PatternDetector()
    results = detector.detect_in_files([f], repo_root=tmp_path)
    assert any("External API" in r for r in results)


# ── Env / secrets ─────────────────────────────────────────────────────────────

def test_detects_os_environ():
    results = _detect("secret = os.environ['SECRET_KEY']")
    assert any("Env/secrets" in r for r in results)


def test_detects_process_env(tmp_path):
    f = tmp_path / "config.js"
    f.write_text("const key = process.env.API_KEY;")
    detector = PatternDetector()
    results = detector.detect_in_files([f], repo_root=tmp_path)
    assert any("Env/secrets" in r for r in results)


def test_detects_load_dotenv():
    results = _detect("from dotenv import load_dotenv\nload_dotenv()")
    assert any("Env/secrets" in r for r in results)


# ── No false positives ────────────────────────────────────────────────────────

def test_no_false_positive_on_plain_code():
    results = _detect("def add(a, b):\n    return a + b\n")
    assert results == [], f"Unexpected patterns: {results}"


# ── Chunk-level detection ─────────────────────────────────────────────────────

def test_detect_in_chunks():
    chunk = CodeChunk(
        file_path="app/db.py",
        chunk_type="function",
        name="run_query",
        content='cursor.execute("SELECT * FROM users")',
        start_line=1,
        end_line=3,
    )
    detector = PatternDetector()
    results = detector.detect_in_chunks([chunk])
    assert any("Raw SQL" in r for r in results)


# ── NEW: Subprocess / system calls ────────────────────────────────────────────

def test_detects_subprocess_run():
    results = _detect("subprocess.run(['ls', '-la'], capture_output=True)")
    assert any("Subprocess" in r for r in results)


def test_detects_os_system():
    results = _detect("os.system('rm -rf /tmp/old_data')")
    assert any("Subprocess" in r for r in results)


def test_detects_eval():
    results = _detect("result = eval(user_input)")
    assert any("Subprocess" in r for r in results)


def test_detects_exec_call():
    results = _detect("exec(compiled_code)")
    assert any("Subprocess" in r for r in results)


# ── NEW: File I/O ─────────────────────────────────────────────────────────────

def test_detects_open_builtin():
    results = _detect("with open('data.csv', 'r') as f:\n    data = f.read()")
    assert any("File I/O" in r for r in results)


def test_detects_fs_readfile_js(tmp_path):
    f = tmp_path / "reader.js"
    f.write_text("fs.readFile('./config.json', 'utf8', callback)")
    detector = PatternDetector()
    results = detector.detect_in_files([f], repo_root=tmp_path)
    assert any("File I/O" in r for r in results)


def test_detects_fs_writefile_js(tmp_path):
    f = tmp_path / "writer.js"
    f.write_text("fs.writeFile('./output.txt', data, callback)")
    detector = PatternDetector()
    results = detector.detect_in_files([f], repo_root=tmp_path)
    assert any("File I/O" in r for r in results)


# ── NEW: Hardcoded secrets ────────────────────────────────────────────────────

def test_detects_api_key_literal():
    results = _detect('API_KEY = "sk-abcdefghijklmnopqrstuvwxyz123456"')
    assert any("Hardcoded secret" in r for r in results)


def test_detects_password_literal():
    results = _detect('password = "mysecretpassword"')
    assert any("Hardcoded secret" in r for r in results)


def test_detects_sk_prefix_key():
    results = _detect('token = "sk-12345678901234567890123456789012"')
    assert any("Hardcoded secret" in r for r in results)


def test_no_false_positive_env_variable_reference():
    # Using os.getenv is NOT a hardcoded secret
    results = _detect('api_key = os.getenv("API_KEY")')
    assert not any("Hardcoded secret" in r for r in results)


# ── NEW: TODO/FIXME/HACK comments ────────────────────────────────────────────

def test_detects_todo_comment():
    results = _detect("# TODO: implement proper validation\nx = 1")
    assert any("TODO/FIXME" in r for r in results)


def test_detects_fixme_comment():
    results = _detect("# FIXME: this crashes on empty input\ndef f(): pass")
    assert any("TODO/FIXME" in r for r in results)


def test_detects_hack_comment():
    results = _detect("# HACK: workaround for library bug\nreturn None")
    assert any("TODO/FIXME" in r for r in results)


def test_detects_js_todo_comment(tmp_path):
    f = tmp_path / "app.js"
    f.write_text("// TODO: refactor this function\nfunction foo() {}")
    detector = PatternDetector()
    results = detector.detect_in_files([f], repo_root=tmp_path)
    assert any("TODO/FIXME" in r for r in results)


# ── Chunk-level: new categories ───────────────────────────────────────────────

def test_detect_subprocess_in_chunk():
    from app.agents.code_chunking_agent import CodeChunk
    chunk = CodeChunk(
        file_path="app/runner.py",
        chunk_type="function",
        name="run_script",
        content="subprocess.run(['bash', 'script.sh'])",
        start_line=1,
        end_line=2,
    )
    detector = PatternDetector()
    results = detector.detect_in_chunks([chunk])
    assert any("Subprocess" in r for r in results)
