"""
Agent 5 — Match Analyst  (Phase 2, runs after Phase 1 completes).

Combines the Phase-1 artefacts (fixtures, form, h2h, squads) into a prediction
for every fixture: win/draw/loss probabilities, a predicted outcome, a
confidence %, and a transparent rationale.

The model is a deliberately explainable weighted score. Each signal produces an
"edge" in [-1, +1] (positive favours the home side). Missing signals are simply
dropped and the remaining weights are renormalised, so the model always works
with whatever data Phase 1 managed to gather.
"""

from agents.base import BaseAgent
from config import (
    ANALYSIS_JSON,
    FIXTURES_JSON,
    FORM_JSON,
    H2H_JSON,
    HOST_NATIONS,
    SQUADS_JSON,
    WEIGHTS,
)
from core.storage import load_json, save_json


class MatchAnalyst(BaseAgent):
    name = "match_analyst"

    def run(self, **kwargs):
        fixtures_doc = load_json(FIXTURES_JSON, default={"fixtures": []})
        fixtures = fixtures_doc.get("fixtures", [])
        form = load_json(FORM_JSON, default={"teams": {}}).get("teams", {})
        h2h = load_json(H2H_JSON, default={"matches": {}}).get("matches", {})
        squads = load_json(SQUADS_JSON, default={"teams": {}}).get("teams", {})

        self.log.info("Analysing %d fixture(s)", len(fixtures))
        analyses = []
        for fx in fixtures:
            analyses.append(self._analyse(fx, form, h2h, squads))

        payload = {
            "is_sample": fixtures_doc.get("is_sample", False),
            "source": fixtures_doc.get("source", "unknown"),
            "generated_at": fixtures_doc.get("generated_at"),
            "weights": WEIGHTS,
            "analyses": analyses,
        }
        save_json(ANALYSIS_JSON, payload)
        return payload

    # ------------------------------------------------------------------ #
    def _analyse(self, fx, form, h2h, squads):
        home, away = fx.get("home"), fx.get("away")

        edges = {}   # component -> signed edge in [-1, 1]
        rationale = []

        f_edge = self._form_edge(home, away, form, rationale)
        if f_edge is not None:
            edges["form"] = f_edge

        h_edge = self._h2h_edge(fx.get("match_id"), h2h, home, away, rationale)
        if h_edge is not None:
            edges["h2h"] = h_edge

        s_edge = self._squad_edge(home, away, squads, rationale)
        if s_edge is not None:
            edges["squad"] = s_edge

        host_edge = self._host_edge(home, away, rationale)
        edges["host"] = host_edge  # always present (0 if neither is a host)

        score = self._weighted_score(edges)
        probs = self._to_probabilities(score)
        pick, confidence = self._pick(probs, home, away)

        return {
            "match_id": fx.get("match_id"),
            "home": home,
            "away": away,
            "date": fx.get("date"),
            "stage": fx.get("stage"),
            "edges": {k: round(v, 3) for k, v in edges.items()},
            "used_weights": self._effective_weights(edges),
            "score": round(score, 3),
            "probabilities": probs,
            "prediction": pick,
            "confidence": confidence,
            "rationale": rationale,
        }

    # ---- individual signals ------------------------------------------- #
    def _form_edge(self, home, away, form, rationale):
        h, a = form.get(home), form.get(away)
        if not (h and a and h.get("results") and a.get("results")):
            rationale.append("Form: insufficient data — signal skipped.")
            return None
        h_ppg = self._ppg(h["summary"])
        a_ppg = self._ppg(a["summary"])
        edge = self._clamp((h_ppg - a_ppg) / 3.0)
        rationale.append(
            f"Form: {home} {h_ppg:.2f} pts/game vs {away} {a_ppg:.2f} — "
            f"{self._favour(edge, home, away)}."
        )
        return edge

    def _h2h_edge(self, match_id, h2h, home, away, rationale):
        rec = (h2h.get(match_id) or {}).get("all_time")
        if not rec or not rec.get("played"):
            rationale.append("Head-to-head: no all-time record — signal skipped.")
            return None
        played = rec["played"]
        edge = self._clamp((rec["home_wins"] - rec["away_wins"]) / played)
        rationale.append(
            f"H2H ({rec['source']}): {played} meetings, {home} "
            f"{rec['home_wins']}W-{rec['draws']}D-{rec['away_wins']}L — "
            f"{self._favour(edge, home, away)}."
        )
        return edge

    def _squad_edge(self, home, away, squads, rationale):
        h, a = squads.get(home), squads.get(away)
        if not (h and a):
            rationale.append("Squad: insufficient data — signal skipped.")
            return None
        h_str = self._squad_strength(h)
        a_str = self._squad_strength(a)
        total = h_str + a_str
        if total <= 0:
            return None
        edge = self._clamp((h_str - a_str) / total)
        rationale.append(
            f"Squad: attacking/experience index {home} {h_str:.0f} vs "
            f"{away} {a_str:.0f} — {self._favour(edge, home, away)}."
        )
        return edge

    def _host_edge(self, home, away, rationale):
        if home in HOST_NATIONS:
            rationale.append(f"Host advantage: {home} playing on home soil.")
            return 1.0
        if away in HOST_NATIONS:
            rationale.append(f"Host advantage: {away} playing on home soil.")
            return -1.0
        rationale.append("Host advantage: neutral venue, no host nation playing.")
        return 0.0

    # ---- scoring maths ------------------------------------------------ #
    @staticmethod
    def _ppg(summary):
        played = max(summary.get("played", 0), 1)
        return summary.get("points", 0) / played

    @staticmethod
    def _squad_strength(squad):
        """Attacking + experience index from key players, penalised by injuries."""
        players = squad.get("key_players", [])
        goals = sum(p.get("goals", 0) or 0 for p in players)
        caps = sum(p.get("caps", 0) or 0 for p in players)
        strength = goals * 1.0 + caps * 0.1
        strength -= 5 * len(squad.get("injuries", []))  # each injury dents it
        return max(strength, 1.0)

    def _weighted_score(self, edges):
        total_w = sum(WEIGHTS[k] for k in edges)
        if total_w <= 0:
            return 0.0
        return sum(WEIGHTS[k] * v for k, v in edges.items()) / total_w

    def _effective_weights(self, edges):
        total_w = sum(WEIGHTS[k] for k in edges)
        if total_w <= 0:
            return {}
        return {k: round(WEIGHTS[k] / total_w, 3) for k in edges}

    @staticmethod
    def _to_probabilities(score):
        """Map a signed edge in [-1,1] to home/draw/away probabilities."""
        draw = 0.30 - 0.15 * abs(score)      # draws likelier when evenly matched
        remaining = 1.0 - draw
        home = remaining * (0.5 + 0.5 * score)
        away = remaining * (0.5 - 0.5 * score)
        # Round to whole percentages that still sum to 100.
        pcts = {"home": home * 100, "draw": draw * 100, "away": away * 100}
        return _round_to_100(pcts)

    @staticmethod
    def _pick(probs, home, away):
        label = {"home": home, "away": away, "draw": "Draw"}
        best = max(probs, key=probs.get)
        return label[best], probs[best]

    # ---- small helpers ------------------------------------------------ #
    @staticmethod
    def _clamp(x, lo=-1.0, hi=1.0):
        return max(lo, min(hi, x))

    @staticmethod
    def _favour(edge, home, away):
        if abs(edge) < 0.05:
            return "level"
        return f"favours {home}" if edge > 0 else f"favours {away}"


def _round_to_100(pcts):
    """Round a dict of percentages to integers summing to exactly 100."""
    floored = {k: int(v) for k, v in pcts.items()}
    remainder = 100 - sum(floored.values())
    # Hand the leftover points to the largest fractional parts.
    fracs = sorted(pcts, key=lambda k: pcts[k] - floored[k], reverse=True)
    for k in fracs[:remainder]:
        floored[k] += 1
    return floored


def run(**kwargs):
    return MatchAnalyst().execute(**kwargs)
