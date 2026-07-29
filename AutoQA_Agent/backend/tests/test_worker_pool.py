"""
Tests: WorkerPool (run_concurrent)

Coverage
- Tasks complete successfully and results are returned in order
- Timed-out tasks return fallback value (not raise)
- Failed tasks return fallback value (not propagate)
- Concurrency is bounded (semaphore respected)
- Empty task list returns empty list
"""
import sys
import os
import asyncio
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://postgres:test@localhost:5432/test")

from app.services.worker_pool import run_concurrent


async def _ok(value):
    await asyncio.sleep(0)
    return value


async def _slow(delay: float, value):
    await asyncio.sleep(delay)
    return value


async def _fail(exc: Exception):
    raise exc


# ── Basic correctness ─────────────────────────────────────────────────────────

def test_empty_returns_empty():
    result = asyncio.run(run_concurrent([]))
    assert result == []


def test_results_in_order():
    tasks = [_ok(i) for i in range(5)]
    results = asyncio.run(run_concurrent(tasks, max_concurrency=3))
    assert results == [0, 1, 2, 3, 4]


# ── Timeout handling ──────────────────────────────────────────────────────────

def test_timeout_produces_fallback():
    def fallback(idx, exc):
        return f"fallback_{idx}"

    tasks = [
        _slow(10.0, "should_timeout"),  # will timeout
        _ok("fast"),
    ]
    results = asyncio.run(
        run_concurrent(tasks, max_concurrency=2, timeout_seconds=0.05, fallback_fn=fallback)
    )
    assert results[0] == "fallback_0"
    assert results[1] == "fast"


def test_timeout_default_fallback_is_none():
    tasks = [_slow(10.0, "x")]
    results = asyncio.run(
        run_concurrent(tasks, max_concurrency=1, timeout_seconds=0.05)
    )
    assert results[0] is None


# ── Exception handling ────────────────────────────────────────────────────────

def test_exception_does_not_abort_batch():
    def fallback(idx, exc):
        return "recovered"

    tasks = [
        _fail(ValueError("boom")),
        _ok("good"),
    ]
    results = asyncio.run(
        run_concurrent(tasks, max_concurrency=2, timeout_seconds=5, fallback_fn=fallback)
    )
    assert results[0] == "recovered"
    assert results[1] == "good"


def test_all_fail_returns_all_fallbacks():
    def fallback(idx, exc):
        return idx * -1

    tasks = [_fail(RuntimeError(f"err {i}")) for i in range(4)]
    results = asyncio.run(
        run_concurrent(tasks, max_concurrency=4, timeout_seconds=5, fallback_fn=fallback)
    )
    assert results == [0, -1, -2, -3]


# ── Concurrency bound ─────────────────────────────────────────────────────────

def test_concurrency_bounded():
    """
    With max_concurrency=2 and 4 slow tasks of 0.1s each, total time
    should be ~0.2s (two batches of 2), not ~0.1s (all at once).
    If semaphore is working, time >= 0.15s.
    """
    tasks = [_slow(0.12, i) for i in range(4)]
    start = time.perf_counter()
    results = asyncio.run(run_concurrent(tasks, max_concurrency=2, timeout_seconds=5))
    elapsed = time.perf_counter() - start
    assert results == [0, 1, 2, 3]
    assert elapsed >= 0.15, f"Too fast ({elapsed:.2f}s) — semaphore may not be working"
