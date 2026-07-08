"""
BaseAgent — the common contract every pipeline agent implements.

Each agent:
  * has a short `name` used for logging and the run summary,
  * implements `run()` which does its work and returns a JSON-serialisable result,
  * wraps `run()` in `execute()` which adds timing, logging, and top-level
    error handling so one failing agent never takes down the pipeline.

Agents deliberately do NOT raise on source failure — they return partial
results with a `status` flag so downstream stages can degrade gracefully.
"""

import time
import traceback

from core.logger import get_logger


class AgentError(Exception):
    """Raised for unrecoverable agent errors (rare — most are handled inline)."""


class BaseAgent:
    #: Human-readable agent name, overridden by subclasses.
    name = "base"

    def __init__(self):
        self.log = get_logger(f"agent:{self.name}")

    # ------------------------------------------------------------------ #
    # Subclasses implement this.
    # ------------------------------------------------------------------ #
    def run(self, **kwargs):
        raise NotImplementedError

    # ------------------------------------------------------------------ #
    # Orchestrator calls this.
    # ------------------------------------------------------------------ #
    def execute(self, **kwargs):
        """Run the agent with timing + error isolation. Always returns a dict."""
        self.log.info("▶ %s starting", self.name)
        start = time.perf_counter()
        try:
            result = self.run(**kwargs)
            elapsed = time.perf_counter() - start
            self.log.info("✔ %s finished in %.2fs", self.name, elapsed)
            return {"agent": self.name, "ok": True, "elapsed": round(elapsed, 2),
                    "result": result}
        except Exception as exc:  # noqa: BLE001 - deliberate top-level guard
            elapsed = time.perf_counter() - start
            self.log.error("x %s crashed after %.2fs: %s", self.name, elapsed, exc)
            self.log.debug(traceback.format_exc())
            return {"agent": self.name, "ok": False, "elapsed": round(elapsed, 2),
                    "error": str(exc), "result": None}

    # ------------------------------------------------------------------ #
    # Small shared helper for tagging partial/degraded records.
    # ------------------------------------------------------------------ #
    @staticmethod
    def degraded(reason, **extra):
        """Build a standard 'this data is incomplete' marker."""
        rec = {"status": "unavailable", "reason": reason}
        rec.update(extra)
        return rec
