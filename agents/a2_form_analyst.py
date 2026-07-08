"""
Agent 2 — Form Analyst  (Phase 1, runs in parallel with Agents 3 & 4).

For every team appearing in the fixtures, assemble their recent form: up to
`FORM_MATCH_COUNT` most-recent results with W/D/L, score and opponent.

Primary source: the completed matches already parsed from the WC2026 page
(real, self-consistent). If a team has no scraped matches, degrade to the
bundled sample form; if that's also missing, emit a clear 'unavailable' record.
"""

from agents.base import BaseAgent
from agents.sample_data import SAMPLE_FORM
from agents.wc_results import parse_played_matches
from config import FORM_JSON, FORM_MATCH_COUNT
from core.storage import load_json, save_json
from config import FIXTURES_JSON


class FormAnalyst(BaseAgent):
    name = "form_analyst"

    def run(self, fixtures=None, **kwargs):
        fixtures = fixtures or self._load_fixtures()
        teams = self._teams_from_fixtures(fixtures)
        self.log.info("Building form for %d team(s): %s", len(teams), ", ".join(teams))

        played = parse_played_matches()
        self.log.debug("Have %d tournament results to mine for form", len(played))

        form = {}
        for team in teams:
            form[team] = self._form_for_team(team, played)

        payload = {"teams": form, "form_window": FORM_MATCH_COUNT}
        save_json(FORM_JSON, payload)
        return payload

    # ------------------------------------------------------------------ #
    def _form_for_team(self, team, played):
        matches = []
        for m in played:
            if team == m["home"]:
                matches.append(self._as_result(team, m, is_home=True))
            elif team == m["away"]:
                matches.append(self._as_result(team, m, is_home=False))

        # Most recent first (dates are ISO strings, empties sort last).
        matches.sort(key=lambda r: r["date"] or "0000", reverse=True)
        matches = matches[:FORM_MATCH_COUNT]

        if matches:
            return {"status": "ok", "source": "wikipedia",
                    "results": matches, "summary": self._summarise(matches)}

        # Fallback: bundled sample form.
        if team in SAMPLE_FORM:
            self.log.warning("No live form for %s — using SAMPLE form", team)
            results = SAMPLE_FORM[team][:FORM_MATCH_COUNT]
            return {"status": "sample", "source": "sample",
                    "results": results, "summary": self._summarise(results)}

        self.log.warning("No form data available for %s", team)
        return self.degraded(f"no results found for {team}", results=[],
                             summary={"W": 0, "D": 0, "L": 0, "points": 0})

    @staticmethod
    def _as_result(team, m, is_home):
        gf, ga = (m["home_score"], m["away_score"]) if is_home else (m["away_score"], m["home_score"])
        opponent = m["away"] if is_home else m["home"]
        result = "W" if gf > ga else "D" if gf == ga else "L"
        return {
            "date": m["date"],
            "opponent": opponent,
            "venue": "H" if is_home else "A",
            "result": result,
            "score": f"{gf}-{ga}",
            "comp": m["stage"] or "World Cup",
        }

    @staticmethod
    def _summarise(results):
        w = sum(1 for r in results if r["result"] == "W")
        d = sum(1 for r in results if r["result"] == "D")
        l = sum(1 for r in results if r["result"] == "L")
        return {"W": w, "D": d, "L": l, "points": w * 3 + d, "played": len(results)}

    # ------------------------------------------------------------------ #
    @staticmethod
    def _teams_from_fixtures(fixtures):
        teams = []
        for fx in fixtures:
            for side in ("home", "away"):
                if fx.get(side) and fx[side] not in teams:
                    teams.append(fx[side])
        return teams

    @staticmethod
    def _load_fixtures():
        data = load_json(FIXTURES_JSON, default={"fixtures": []})
        return data.get("fixtures", [])


def run(**kwargs):
    return FormAnalyst().execute(**kwargs)
