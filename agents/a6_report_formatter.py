"""
Agent 6 — Report Formatter  (Phase 2, runs last).

Assembles every Phase-1/2 artefact into a single view-model and renders the
Jinja2 template to reports/worldcup_analysis_<date>.html.

Pure presentation: it does no scraping and no prediction — it only joins the
JSON produced upstream and formats it beautifully.
"""

from datetime import datetime

from jinja2 import Environment, FileSystemLoader, select_autoescape

from agents.base import BaseAgent
from config import (
    ANALYSIS_JSON,
    DEFAULT_TEAM_COLOR,
    FIXTURES_JSON,
    FORM_JSON,
    H2H_JSON,
    REPORTS_DIR,
    SQUADS_JSON,
    TEAM_COLORS,
    TEMPLATES_DIR,
    all_flags,
)
from core.storage import load_json


class ReportFormatter(BaseAgent):
    name = "report_formatter"

    def run(self, **kwargs):
        analysis = load_json(ANALYSIS_JSON, default={"analyses": []})
        form = load_json(FORM_JSON, default={"teams": {}}).get("teams", {})
        h2h = load_json(H2H_JSON, default={"matches": {}}).get("matches", {})
        squads = load_json(SQUADS_JSON, default={"teams": {}}).get("teams", {})
        fixtures = load_json(FIXTURES_JSON, default={"fixtures": []}).get("fixtures", [])
        fx_by_id = {f.get("match_id"): f for f in fixtures}

        analyses = analysis.get("analyses", [])
        self.log.info("Formatting report for %d match(es)", len(analyses))

        matches = [self._build_match(a, form, h2h, squads, fx_by_id) for a in analyses]
        html = self._render(analysis, matches)

        out_path = REPORTS_DIR / f"worldcup_analysis_{datetime.now():%Y-%m-%d}.html"
        out_path.write_text(html, encoding="utf-8")
        self.log.info("Report written -> %s", out_path)
        return {"report_path": str(out_path), "matches": len(matches),
                "is_sample": analysis.get("is_sample", False)}

    # ------------------------------------------------------------------ #
    def _build_match(self, a, form, h2h, squads, fx_by_id):
        home, away = a["home"], a["away"]
        fx = fx_by_id.get(a["match_id"], {})
        h2h_rec = (h2h.get(a["match_id"]) or {}).get("all_time")
        return {
            "match_id": a["match_id"],
            "home": home,
            "away": away,
            "stage": a.get("stage") or fx.get("stage"),
            "date_label": self._date_label(a.get("date")),
            "time": fx.get("time", ""),
            "venue": fx.get("venue", ""),
            "city": fx.get("city", ""),
            "prediction": a["prediction"],
            "confidence": a["confidence"],
            "prob": a["probabilities"],
            "rationale": a["rationale"],
            "home_form": form.get(home),
            "away_form": form.get(away),
            "home_squad": squads.get(home),
            "away_squad": squads.get(away),
            "h2h": h2h_rec,
        }

    def _render(self, analysis, matches):
        env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True, lstrip_blocks=True,
        )
        template = env.get_template("report.html.j2")
        return template.render(
            matches=matches,
            is_sample=analysis.get("is_sample", False),
            source_label=self._source_label(analysis.get("source")),
            generated_at=datetime.now().strftime("%d %b %Y, %H:%M"),
            generated_date=datetime.now().strftime("%Y-%m-%d"),
            weights=analysis.get("weights", {}),
            flags=all_flags(),
            colors=TEAM_COLORS,
            default_color=DEFAULT_TEAM_COLOR,
        )

    # ---- small formatting helpers ------------------------------------ #
    @staticmethod
    def _date_label(iso):
        if not iso:
            return "Date TBC"
        try:
            return datetime.strptime(iso, "%Y-%m-%d").strftime("%a %d %b %Y")
        except (ValueError, TypeError):
            return iso

    @staticmethod
    def _source_label(source):
        return {"wikipedia": "Wikipedia (live)", "sample": "Bundled sample"}.get(
            source, source or "unknown")


def run(**kwargs):
    return ReportFormatter().execute(**kwargs)
