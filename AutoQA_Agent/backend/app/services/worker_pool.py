"""
WorkerPool — async concurrency harness for Ollama batch jobs.

Design
------
- `run_concurrent` limits simultaneous coroutines via asyncio.Semaphore.
- Each task runs with a per-task timeout (settings.ollama_chunk_timeout_seconds).
- If a task times out or raises, a heuristic fallback result is returned for
  that task only — the rest of the batch is unaffected.
- The returned list is always the same length as `tasks` and in the same order
  (asyncio.gather with return_exceptions semantics, then mapped to results).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Coroutine

from app.core.config import settings

logger = logging.getLogger(__name__)


async def run_concurrent(
    tasks: list[Coroutine],
    max_concurrency: int | None = None,
    timeout_seconds: float | None = None,
    fallback_fn: Callable[[int, Exception], Any] | None = None,
) -> list[Any]:
    """
    Run a list of coroutines concurrently with bounded concurrency and per-task
    timeouts.

    Parameters
    ----------
    tasks           : coroutines to execute
    max_concurrency : cap on simultaneous tasks (default: settings.ollama_max_concurrency)
    timeout_seconds : per-task timeout in seconds (default: settings.ollama_chunk_timeout_seconds)
    fallback_fn     : called as fallback_fn(task_index, exc) on failure; returns
                      a fallback result for that slot. Defaults to returning None.

    Returns
    -------
    List of results in the same order as `tasks`. Failed slots contain
    fallback_fn's return value (default: None).
    """
    if not tasks:
        return []

    max_con = max_concurrency if max_concurrency is not None else getattr(settings, "cloud_max_concurrency", settings.ollama_max_concurrency)
    timeout  = timeout_seconds if timeout_seconds is not None else float(getattr(settings, "cloud_chunk_timeout_seconds", settings.ollama_chunk_timeout_seconds))

    semaphore = asyncio.Semaphore(max_con)
    results: list[Any] = [None] * len(tasks)

    async def _run_one(index: int, coro: Coroutine) -> None:
        async with semaphore:
            try:
                results[index] = await asyncio.wait_for(coro, timeout=timeout)
            except asyncio.TimeoutError:
                exc = asyncio.TimeoutError(f"Task {index} timed out after {timeout}s")
                logger.warning("Worker pool: task %d timed out after %.0fs", index, timeout)
                results[index] = fallback_fn(index, exc) if fallback_fn else None
            except Exception as exc:
                logger.warning("Worker pool: task %d failed: %s", index, exc)
                results[index] = fallback_fn(index, exc) if fallback_fn else None

    await asyncio.gather(*[_run_one(i, coro) for i, coro in enumerate(tasks)])
    return results
