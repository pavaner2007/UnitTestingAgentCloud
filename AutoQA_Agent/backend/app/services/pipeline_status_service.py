"""
PipelineStatusService — in-memory, asyncio-safe pipeline stage tracker.

⚠ IMPORTANT DEPLOYMENT NOTE:
   This service stores state in a module-level dict inside a single Python process.
   It is asyncio-safe (all mutations happen synchronously within the event loop —
   no threading required because FastAPI + Uvicorn run inside a single asyncio loop).
   However, it is NOT safe for multi-worker deployments:
   - `uvicorn app.main:app --workers N` (N > 1) will create N separate processes,
     each with their own in-memory dict.  Status updates from the analysis
     BackgroundTask will land in one worker's dict, but the frontend's polling
     requests may be routed to a different worker that has an empty dict.
   - For multi-worker deployments, replace this module with a Redis-backed
     equivalent (e.g. using `redis.asyncio`).
   - For the current single-worker development setup this is completely fine.

TTL / Cleanup:
   Entries expire after TTL_SECONDS (default 3600 s = 1 h).  Expired entries are
   purged lazily on any get_status / set_status call, and can also be explicitly
   removed via remove(analysis_id) once the frontend has retrieved the final report.
"""
from __future__ import annotations

import time
import logging
from threading import Lock

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

TTL_SECONDS: int = 3600   # Entries older than this are eligible for cleanup

# Canonical ordered stage list.  The frontend renders boxes in this exact order.
PIPELINE_STAGES: list[str] = [
    "Clone Repo",
    "Tech Stack Detection",
    "API Discovery",
    "File Prioritization",
    "Semantic Chunking",
    "Embedding Generation",
    "Pattern Detection",
    "Bug Detection",
    "Dependency Graph",
    "Chunk Summarization",
    "Module & File Reduce",
    "Groq AI Reasoning",
    "Change Impact Analysis",
    "Architecture Drift Audit",
    "Developer Onboarding Guide",
    "Repository Health Scoring",
    "Tech Debt Prioritization",
    # V3 Agents
    "Execution Flow Analysis",
    "Feature Extraction",
]

_VALID_STATUSES = frozenset({"queued", "running", "done", "failed", "skipped"})


# ── Service ───────────────────────────────────────────────────────────────────


class PipelineStatusService:
    """
    Manages real-time pipeline stage status for all active analyses.

    Thread / async safety
    ---------------------
    All public methods acquire a threading.Lock.  This is required because
    FastAPI BackgroundTask callbacks run in a thread-pool executor (they are
    called via asyncio.to_thread under the hood), so set_status() can be
    called from a worker thread concurrently with get_status() being called
    from the event-loop thread handling a polling request.

    Structure
    ---------
    _store: {
        analysis_id: {
            "created_at": float,   # time.monotonic() at init_pipeline()
            "stages": {
                stage_name: {"status": str, "preview": str | None}
            }
        }
    }
    """

    def __init__(self) -> None:
        self._store: dict[str, dict] = {}
        self._lock = Lock()

    # ── Public API ────────────────────────────────────────────────────────────

    def init_pipeline(self, analysis_id: str) -> None:
        """Initialise all 12 stages to 'queued'.  Call before spawning the BackgroundTask."""
        with self._lock:
            self._purge_expired()
            self._store[analysis_id] = {
                "created_at": time.monotonic(),
                "stages": {
                    name: {"status": "queued", "preview": None}
                    for name in PIPELINE_STAGES
                },
            }
        logger.debug("PipelineStatus: initialised %s", analysis_id)

    def set_status(
        self,
        analysis_id: str,
        stage_name: str,
        status: str,
        preview: str | None = None,
    ) -> None:
        """
        Update the status (and optional preview string) for a single stage.

        Parameters
        ----------
        analysis_id : str  — the UUID returned to the client
        stage_name  : str  — must be one of PIPELINE_STAGES
        status      : str  — one of: "queued" | "running" | "done" | "failed" | "skipped"
        preview     : str  — short one-line result string shown under the stage card
                             (e.g. "43 files, 12 dirs", "12 patterns found")
        """
        if status not in _VALID_STATUSES:
            logger.warning("PipelineStatus: invalid status %r for stage %r", status, stage_name)
            return
        with self._lock:
            entry = self._store.get(analysis_id)
            if entry is None:
                logger.debug(
                    "PipelineStatus: set_status called for unknown analysis_id %s — ignoring",
                    analysis_id,
                )
                return
            stages = entry["stages"]
            if stage_name not in stages:
                # Tolerate unknown stage names gracefully
                logger.warning("PipelineStatus: unknown stage %r — skipping", stage_name)
                return
            stages[stage_name]["status"] = status
            if preview is not None:
                stages[stage_name]["preview"] = preview
        logger.debug("PipelineStatus: [%s] %s → %s", analysis_id[:8], stage_name, status)

    def fail_remaining(self, analysis_id: str, error_msg: str = "Pipeline error") -> None:
        """
        Mark every stage still in 'queued' or 'running' state as 'failed'.
        Call this in the pipeline's top-level except handler to prevent the
        frontend from polling forever with stages stuck in 'running'.
        """
        with self._lock:
            entry = self._store.get(analysis_id)
            if entry is None:
                return
            for stage in entry["stages"].values():
                if stage["status"] in ("queued", "running"):
                    stage["status"] = "failed"
                    stage["preview"] = error_msg
        logger.warning("PipelineStatus: marked remaining stages failed for %s: %s", analysis_id[:8], error_msg)

    def get_status(self, analysis_id: str) -> dict | None:
        """
        Return the current pipeline state for the frontend polling endpoint.

        Returns None if analysis_id is unknown (expired or never initialised).

        Response shape:
        {
            "analysis_id": str,
            "agents": [{"name": str, "status": str, "preview": str | None}, ...],
            "complete": bool
        }
        complete = True when every stage is "done", "failed", or "skipped".
        """
        with self._lock:
            self._purge_expired()
            entry = self._store.get(analysis_id)
            if entry is None:
                return None
            agents = [
                {"name": name, **data}
                for name, data in entry["stages"].items()
            ]
        terminal = {"done", "failed", "skipped"}
        complete = all(a["status"] in terminal for a in agents)
        return {
            "analysis_id": analysis_id,
            "agents": agents,
            "complete": complete,
        }

    def remove(self, analysis_id: str) -> None:
        """Explicitly remove a completed pipeline entry to free memory immediately."""
        with self._lock:
            self._store.pop(analysis_id, None)
        logger.debug("PipelineStatus: removed entry for %s", analysis_id[:8])

    # ── Private ───────────────────────────────────────────────────────────────

    def _purge_expired(self) -> None:
        """Remove entries older than TTL_SECONDS.  Must be called with self._lock held."""
        now = time.monotonic()
        expired = [
            aid for aid, entry in self._store.items()
            if (now - entry["created_at"]) > TTL_SECONDS
        ]
        for aid in expired:
            del self._store[aid]
            logger.debug("PipelineStatus: TTL-expired entry for %s", aid[:8])


# ── Module-level singleton ────────────────────────────────────────────────────
# One instance per process.  Multiple worker processes → separate instances
# (see module docstring for guidance on multi-worker deployments).

pipeline_status = PipelineStatusService()
