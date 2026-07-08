"""
Tournament data builder for the dashboard.

Produces data/tournament.json — everything the Flask dashboard needs:
  * all matches (results + upcoming) with London kick-off times,
  * group standings,
  * per-team recent form (mined from the full match history),
  * squads (key players, coach) for teams in upcoming matches,
  * a prediction for every playable upcoming fixture,
  * a few tournament-wide stat highlights.

Reused by the CLI (`python build_data.py`) and the Flask "Refresh" button.
"""

from datetime import datetime

from agents import h2h as h2h_mod
from agents import predictions_log as plog
from agents.a2_form_analyst import FormAnalyst
from agents.a4_squad_reporter import SquadReporter
from agents.a5_match_analyst import MatchAnalyst
from agents.wc_tournament import build_tournament
from config import ROOT
from core.http import fetch_soup
from config import WORLD_CUP_2026_SQUADS_WIKI
from core.logger import get_logger, setup_logging
from core.storage import save_json

log = get_logger("build_data")

TOURNAMENT_JSON = "tournament.json"
# Persisted, forward-only prediction log (committed back by the GitHub Action).
PREDICTIONS_LOG_PATH = ROOT / "predictions_log.json"


def build_and_save():
    setup_logging()
    log.info("=== Building full tournament dataset ===")
    tour = build_tournament()
    matches = tour["matches"]

    if not matches:
        log.error("No matches scraped — writing empty dataset")
        payload = _empty_payload()
        save_json(TOURNAMENT_JSON, payload)
        return payload

    # Real completed matches drive form; keep the shape FormAnalyst expects.
    played = [
        {"date": m["date_iso"], "home": m["home"], "away": m["away"],
         "home_score": m["home_score"], "away_score": m["away_score"],
         "stage": (m["group"] or m["stage"])}
        for m in matches if m["played"] and not m["is_tbd"]
    ]

    upcoming = [m for m in matches if not m["played"] and not m["is_tbd"]]
    log.info("%d upcoming playable fixture(s) to predict", len(upcoming))

    teams_in_play = sorted({m["home"] for m in upcoming} | {m["away"] for m in upcoming})

    form = _build_form(teams_in_play, played)
    squads = _build_squads(teams_in_play)
    _predict(upcoming, form, squads)

    # ---- Forward-only prediction log: record new, resolve finished --------- #
    now_iso = datetime.now().isoformat(timespec="seconds")
    pred_log = plog.load_log(PREDICTIONS_LOG_PATH)
    plog.record_predictions(pred_log, upcoming, now_iso)
    plog.resolve(pred_log, matches, now_iso)
    plog.save_log(PREDICTIONS_LOG_PATH, pred_log)

    verdicts = plog.verdicts_by_key(pred_log)
    for m in matches:
        rec = verdicts.get(plog.match_key(m["home"], m["away"], m.get("date_iso")))
        if rec:
            m["verdict"] = {
                "predicted_team": rec["predicted_team"],
                "predicted_side": rec["predicted_side"],
                "correct": rec["correct"],
                "actual_winner": rec.get("actual_winner"),
            }
    accuracy = plog.accuracy(pred_log)
    log.info("Prediction accuracy: %d/%d correct (%d%%)",
             accuracy["correct"], accuracy["resolved"], accuracy["pct"])

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "generated_label": datetime.now().strftime("%d %b %Y, %H:%M"),
        "source": "wikipedia",
        "is_sample": False,
        "stages_order": tour["stages_order"],
        "groups": tour["groups"],
        "matches": matches,
        "teams": {t: {"form": form.get(t), "squad": squads.get(t)} for t in teams_in_play},
        "accuracy": accuracy,
        "stats": _stats(matches, tour["groups"], upcoming),
        "counts": {
            "matches": len(matches),
            "played": sum(1 for m in matches if m["played"]),
            "upcoming": len(upcoming),
            "tbd": sum(1 for m in matches if m["is_tbd"]),
            "groups": len(tour["groups"]),
        },
    }
    save_json(TOURNAMENT_JSON, payload)
    log.info("=== Tournament dataset built: %d matches ===", len(matches))
    return payload


# --------------------------------------------------------------------------- #
def _build_form(teams, played):
    fa = FormAnalyst()
    return {t: fa._form_for_team(t, played) for t in teams}


def _build_squads(teams):
    soup = fetch_soup(WORLD_CUP_2026_SQUADS_WIKI)
    sr = SquadReporter()
    return {t: sr._squad_for(t, soup) for t in teams}


def _predict(upcoming, form, squads):
    analyst = MatchAnalyst()
    for m in upcoming:
        rec = h2h_mod.fetch_h2h(m["home"], m["away"])
        h2h_dict = {m["match_id"]: {"all_time": rec}} if rec else {}
        fx = {"match_id": m["match_id"], "home": m["home"], "away": m["away"],
              "date": m.get("date_iso"), "stage": m.get("stage")}
        analysis = analyst._analyse(fx, form, h2h_dict, squads)
        m["prediction"] = analysis
        m["h2h"] = rec


def _stats(matches, groups, upcoming):
    played = [m for m in matches if m["played"] and not m["is_tbd"]]
    # Biggest goal margins as "upsets"/highlights.
    def margin(m):
        return abs((m["home_score"] or 0) - (m["away_score"] or 0))
    big = sorted(played, key=margin, reverse=True)[:5]
    highlights = [
        {"home": m["home"], "away": m["away"],
         "home_score": m["home_score"], "away_score": m["away_score"],
         "stage": m["group"] or m["stage"]}
        for m in big
    ]
    favourites = [
        {"home": m["home"], "away": m["away"],
         "pick": m["prediction"]["prediction"],
         "confidence": m["prediction"]["confidence"]}
        for m in upcoming if m.get("prediction")
    ]
    favourites.sort(key=lambda x: x["confidence"], reverse=True)
    return {"highlights": highlights, "favourites": favourites,
            "total_goals": sum((m["home_score"] or 0) + (m["away_score"] or 0)
                               for m in played)}


def _empty_payload():
    return {"generated_at": datetime.now().isoformat(timespec="seconds"),
            "generated_label": datetime.now().strftime("%d %b %Y, %H:%M"),
            "source": "unavailable", "is_sample": False, "stages_order": [],
            "groups": [], "matches": [], "teams": {},
            "accuracy": {"resolved": 0, "correct": 0, "pct": 0},
            "stats": {}, "counts": {}}


if __name__ == "__main__":
    build_and_save()
