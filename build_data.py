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
from agents.goalscorers import fetch_top_scorers
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
    teams_all = sorted({m["home"] for m in matches if not m["is_tbd"]}
                       | {m["away"] for m in matches if not m["is_tbd"]})

    form = _build_form(teams_in_play, played)
    squads = _build_squads(teams_all)   # all teams — still a single squads-page fetch
    _predict(upcoming, form, squads)

    # Attach "form going in" to every finished match, computed from results we
    # already have (no extra scraping) so their detail panels are worth opening.
    _attach_finished_form(matches, played)

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
        "teams": {t: {"form": form.get(t), "squad": squads.get(t)} for t in teams_all},
        "accuracy": accuracy,
        "stats": _stats(matches, tour["groups"], upcoming),
        "statspage": _statspage(matches),
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


def _attach_finished_form(matches, played, n=5):
    """For each finished match, attach each team's last N results BEFORE it."""
    fa = FormAnalyst()
    for m in matches:
        if not (m.get("played") and not m.get("is_tbd")):
            continue
        m["home_form"] = _form_before(fa, m["home"], m.get("date_iso"), played, n)
        m["away_form"] = _form_before(fa, m["away"], m.get("date_iso"), played, n)


def _form_before(fa, team, date_iso, played, n):
    """Results for `team` strictly before `date_iso`, most-recent first."""
    out = []
    for pm in played:
        d = pm.get("date")
        if date_iso and d and d >= date_iso:
            continue
        if team == pm["home"]:
            out.append(fa._as_result(team, pm, True))
        elif team == pm["away"]:
            out.append(fa._as_result(team, pm, False))
    out.sort(key=lambda r: r["date"] or "0000", reverse=True)
    return out[:n]


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
    # Soonest match first (sort on the UTC timestamp for correct ordering).
    up_sorted = sorted((m for m in upcoming if m.get("prediction")),
                       key=lambda m: m.get("kickoff_iso") or m.get("date_iso") or "9999")
    favourites = [
        {"home": m["home"], "away": m["away"],
         "pick": m["prediction"]["prediction"],
         "confidence": m["prediction"]["confidence"],
         "kickoff": m.get("kickoff_london") or m.get("date_london") or ""}
        for m in up_sorted
    ]
    return {"highlights": highlights, "favourites": favourites,
            "total_goals": sum((m["home_score"] or 0) + (m["away_score"] or 0)
                               for m in played)}


def _statspage(matches):
    """Top scorers (one fetch) + team & tournament stats (from existing data)."""
    played = [m for m in matches if m["played"] and not m["is_tbd"]
              and m["home_score"] is not None]

    # ---- team tables (no scraping) ---- #
    gf, ga, cs, pl = {}, {}, {}, {}
    def bump(d, k, v): d[k] = d.get(k, 0) + v
    for m in played:
        h, a, hs, as_ = m["home"], m["away"], m["home_score"], m["away_score"]
        bump(gf, h, hs); bump(ga, h, as_); bump(pl, h, 1)
        bump(gf, a, as_); bump(ga, a, hs); bump(pl, a, 1)
        if as_ == 0: bump(cs, h, 1)
        if hs == 0: bump(cs, a, 1)
    teams = list(pl.keys())
    most_goals = [{"team": t, "value": gf.get(t, 0), "played": pl[t]}
                  for t in sorted(teams, key=lambda t: (-gf.get(t, 0), ga.get(t, 0)))[:8]]
    best_def = [{"team": t, "value": ga.get(t, 0), "played": pl[t]}
                for t in sorted(teams, key=lambda t: (ga.get(t, 0), -gf.get(t, 0)))[:8]]
    clean = [{"team": t, "value": cs.get(t, 0), "played": pl[t]}
             for t in sorted(teams, key=lambda t: (-cs.get(t, 0), ga.get(t, 0)))[:8]]

    # ---- tournament totals ---- #
    total_goals = sum(m["home_score"] + m["away_score"] for m in played)
    gpm = round(total_goals / len(played), 2) if played else 0
    pens = sum(1 for m in matches if m.get("pens"))
    bw = max(played, key=lambda m: abs(m["home_score"] - m["away_score"]), default=None)
    biggest = ({"home": bw["home"], "away": bw["away"], "home_score": bw["home_score"],
                "away_score": bw["away_score"], "stage": bw["group"] or bw["stage"]}
               if bw else None)

    return {
        "top_scorers": fetch_top_scorers(),
        "teams": {"most_goals": most_goals, "best_defence": best_def,
                  "clean_sheets": clean},
        "tournament": {"total_goals": total_goals, "goals_per_match": gpm,
                       "penalty_shootouts": pens, "biggest_win": biggest},
    }


def _empty_payload():
    return {"generated_at": datetime.now().isoformat(timespec="seconds"),
            "generated_label": datetime.now().strftime("%d %b %Y, %H:%M"),
            "source": "unavailable", "is_sample": False, "stages_order": [],
            "groups": [], "matches": [], "teams": {},
            "accuracy": {"resolved": 0, "correct": 0, "pct": 0},
            "stats": {}, "statspage": {}, "counts": {}}


if __name__ == "__main__":
    build_and_save()
