"""
World Cup 2026 Match Analyser — pipeline orchestrator.

Runs the six-agent pipeline:

  Phase 1
    Agent 1  Fixtures Scout        (runs first — everything else needs fixtures)
    Agents 2/3/4  Form · H2H · Squad   (run IN PARALLEL on the fixture list)

  Phase 2
    Agent 5  Match Analyst         (combines everything → predictions)
    Agent 6  Report Formatter      (renders the HTML report)

Every agent is isolated: a failure is logged and the pipeline carries on using
whatever JSON artefacts are available, so one bad source never kills the run.

Usage:  python run.py
"""

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from agents import (
    a1_fixtures_scout,
    a2_form_analyst,
    a3_h2h_historian,
    a4_squad_reporter,
    a5_match_analyst,
    a6_report_formatter,
)
from core.logger import get_logger, setup_logging

log = get_logger("orchestrator")


def _banner(title):
    log.info("=" * 58)
    log.info(title)
    log.info("=" * 58)


def run_pipeline():
    log_path = setup_logging()
    _banner("WORLD CUP 2026 MATCH ANALYSER — pipeline start")
    log.info("Full log: %s", log_path)

    summary = []

    # ---- Phase 1a: Fixtures Scout (must run first) -------------------- #
    _banner("PHASE 1a — Fixtures Scout")
    scout_res = a1_fixtures_scout.run()
    summary.append(scout_res)
    fixtures = (scout_res.get("result") or {}).get("fixtures", [])
    if not fixtures:
        log.error("No fixtures produced — aborting pipeline.")
        return _finish(summary, report_path=None)
    log.info("Scout returned %d fixture(s) [source=%s]",
             len(fixtures), (scout_res.get("result") or {}).get("source"))

    # Warm the shared results cache once (single-threaded) so the parallel
    # Form and H2H agents don't race to fetch the same pages.
    from agents.wc_results import parse_played_matches
    parse_played_matches()

    # ---- Phase 1b: Form / H2H / Squad in parallel -------------------- #
    _banner("PHASE 1b — Form · H2H · Squad (parallel)")
    parallel_agents = {
        "form": a2_form_analyst,
        "h2h": a3_h2h_historian,
        "squad": a4_squad_reporter,
    }
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            pool.submit(mod.run, fixtures=fixtures): key
            for key, mod in parallel_agents.items()
        }
        for fut in as_completed(futures):
            key = futures[fut]
            try:
                summary.append(fut.result())
            except Exception as exc:  # noqa: BLE001 - already guarded in agents
                log.error("Parallel agent '%s' raised: %s", key, exc)
                summary.append({"agent": key, "ok": False, "error": str(exc)})

    # ---- Phase 2: Analyst then Report -------------------------------- #
    _banner("PHASE 2 — Match Analyst → Report Formatter")
    summary.append(a5_match_analyst.run())
    report_res = a6_report_formatter.run()
    summary.append(report_res)

    report_path = (report_res.get("result") or {}).get("report_path")
    return _finish(summary, report_path)


def _finish(summary, report_path):
    _banner("PIPELINE SUMMARY")
    for s in summary:
        status = "OK " if s.get("ok") else "FAIL"
        elapsed = s.get("elapsed", "?")
        log.info("  [%s] %-18s %ss", status, s.get("agent", "?"), elapsed)
    ok = sum(1 for s in summary if s.get("ok"))
    log.info("%d/%d agents succeeded", ok, len(summary))
    if report_path:
        log.info("REPORT: %s", report_path)
    else:
        log.warning("No report produced.")
    return report_path


if __name__ == "__main__":
    path = run_pipeline()
    sys.exit(0 if path else 1)
