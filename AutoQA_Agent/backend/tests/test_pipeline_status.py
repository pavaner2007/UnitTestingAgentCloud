"""
Unit tests for PipelineStatusService.

These tests cover:
- init_pipeline creates all 12 stages as "queued"
- set_status updates status and preview correctly
- get_status returns the correct shape and `complete` flag
- fail_remaining marks all non-terminal stages as "failed"
- TTL expiry (via monkey-patching time.monotonic)
- remove() explicit cleanup
- Thread safety (basic concurrent write test)
"""
import time
import threading
from unittest.mock import patch

import pytest

from app.services.pipeline_status_service import (
    PipelineStatusService,
    PIPELINE_STAGES,
    TTL_SECONDS,
)


@pytest.fixture()
def svc():
    """Fresh service instance per test (avoids cross-test state sharing)."""
    return PipelineStatusService()


# ── init ──────────────────────────────────────────────────────────────────────

def test_init_creates_all_stages_as_queued(svc):
    svc.init_pipeline("abc")
    result = svc.get_status("abc")
    assert result is not None
    names = [a["name"] for a in result["agents"]]
    assert names == PIPELINE_STAGES
    for agent in result["agents"]:
        assert agent["status"] == "queued"
        assert agent["preview"] is None


def test_init_not_complete(svc):
    svc.init_pipeline("abc")
    assert svc.get_status("abc")["complete"] is False


# ── set_status ────────────────────────────────────────────────────────────────

def test_set_status_updates_status(svc):
    svc.init_pipeline("x")
    svc.set_status("x", "Clone Repo", "running")
    agents = svc.get_status("x")["agents"]
    clone = next(a for a in agents if a["name"] == "Clone Repo")
    assert clone["status"] == "running"


def test_set_status_updates_preview(svc):
    svc.init_pipeline("x")
    svc.set_status("x", "Clone Repo", "done", preview="42 files")
    agents = svc.get_status("x")["agents"]
    clone = next(a for a in agents if a["name"] == "Clone Repo")
    assert clone["preview"] == "42 files"


def test_set_status_invalid_status_ignored(svc):
    svc.init_pipeline("x")
    svc.set_status("x", "Clone Repo", "INVALID_STATUS")
    agents = svc.get_status("x")["agents"]
    clone = next(a for a in agents if a["name"] == "Clone Repo")
    # Should still be queued (original state), not updated
    assert clone["status"] == "queued"


def test_set_status_unknown_stage_ignored(svc):
    svc.init_pipeline("x")
    svc.set_status("x", "Nonexistent Stage", "done")  # should not raise
    result = svc.get_status("x")
    assert result is not None  # no crash


def test_set_status_unknown_analysis_id_ignored(svc):
    # Should not raise even if analysis_id doesn't exist
    svc.set_status("does-not-exist", "Clone Repo", "done")


# ── complete flag ─────────────────────────────────────────────────────────────

def test_complete_when_all_done(svc):
    svc.init_pipeline("y")
    for stage in PIPELINE_STAGES:
        svc.set_status("y", stage, "done")
    assert svc.get_status("y")["complete"] is True


def test_complete_with_mixed_terminal_states(svc):
    svc.init_pipeline("y")
    for i, stage in enumerate(PIPELINE_STAGES):
        svc.set_status("y", stage, "done" if i % 2 == 0 else "failed")
    assert svc.get_status("y")["complete"] is True


def test_not_complete_when_one_running(svc):
    svc.init_pipeline("y")
    for stage in PIPELINE_STAGES:
        svc.set_status("y", stage, "done")
    svc.set_status("y", PIPELINE_STAGES[-1], "running")
    assert svc.get_status("y")["complete"] is False


# ── fail_remaining ────────────────────────────────────────────────────────────

def test_fail_remaining_marks_queued_and_running(svc):
    svc.init_pipeline("z")
    svc.set_status("z", PIPELINE_STAGES[0], "done")
    svc.set_status("z", PIPELINE_STAGES[1], "running")
    # All others are queued
    svc.fail_remaining("z", error_msg="pipeline error")

    agents = {a["name"]: a for a in svc.get_status("z")["agents"]}
    # done stays done
    assert agents[PIPELINE_STAGES[0]]["status"] == "done"
    # running and queued become failed
    for stage in PIPELINE_STAGES[1:]:
        assert agents[stage]["status"] == "failed"
        assert agents[stage]["preview"] == "pipeline error"


def test_fail_remaining_unknown_id_does_not_raise(svc):
    svc.fail_remaining("does-not-exist")  # should not raise


# ── remove + TTL ──────────────────────────────────────────────────────────────

def test_remove_clears_entry(svc):
    svc.init_pipeline("r")
    svc.remove("r")
    assert svc.get_status("r") is None


def test_get_status_returns_none_for_unknown(svc):
    assert svc.get_status("never-initialised") is None


def test_ttl_expiry_removes_old_entry(svc):
    svc.init_pipeline("ttl-test")
    # Fake monotonic so that the entry looks 1 second past TTL
    old_time = time.monotonic() - TTL_SECONDS - 1
    with patch.object(svc, "_store") as mock_store:
        mock_store.__contains__ = lambda self, k: k == "ttl-test"
        mock_store.items = lambda: [("ttl-test", {"created_at": old_time, "stages": {}})]
        mock_store.get = lambda k, d=None: {"created_at": old_time, "stages": {}} if k == "ttl-test" else d
        # Directly test _purge_expired behaviour by re-initialising with real store
    # Use real store with a mocked created_at
    svc._store["ttl-test"]["created_at"] = time.monotonic() - TTL_SECONDS - 1
    svc.init_pipeline("trigger-purge")  # triggers _purge_expired inside init
    assert svc.get_status("ttl-test") is None


# ── thread safety ─────────────────────────────────────────────────────────────

def test_concurrent_set_status_does_not_corrupt_state(svc):
    """Basic smoke test: 20 threads writing simultaneously should not raise or corrupt."""
    svc.init_pipeline("concurrent")

    errors = []

    def worker(stage, status):
        try:
            svc.set_status("concurrent", stage, status)
        except Exception as exc:
            errors.append(exc)

    threads = [
        threading.Thread(target=worker, args=(stage, "done"))
        for stage in PIPELINE_STAGES
        for _ in range(2)  # 2 threads per stage = 24 concurrent writes
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], f"Thread errors: {errors}"
    result = svc.get_status("concurrent")
    assert result is not None
    # All stages should be "done" (all writes use "done")
    for agent in result["agents"]:
        assert agent["status"] == "done"


# ── stage count ───────────────────────────────────────────────────────────────

def test_pipeline_stages_count():
    assert len(PIPELINE_STAGES) == 19


def test_pipeline_stages_has_expected_stages():
    expected = {
        "Clone Repo", "Tech Stack Detection", "API Discovery",
        "File Prioritization", "Semantic Chunking", "Embedding Generation",
        "Pattern Detection", "Bug Detection", "Dependency Graph",
        "Chunk Summarization", "Module & File Reduce", "Groq AI Reasoning",
        "Change Impact Analysis", "Architecture Drift Audit",
        "Developer Onboarding Guide", "Repository Health Scoring",
        "Tech Debt Prioritization", "Execution Flow Analysis",
        "Feature Extraction",
    }
    assert set(PIPELINE_STAGES) == expected
