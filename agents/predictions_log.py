"""
Forward-only prediction log + verdict resolution.

Every build:
  * records a prediction for each currently-upcoming match (once, before it's
    played) — so the record is a genuine *pre-match* prediction,
  * resolves any previously-logged prediction whose match has since finished,
    marking it correct/wrong against the real result.

The log is persisted to `predictions_log.json` at the repo root and committed
back by the GitHub Action, so verdicts and accuracy accumulate permanently and
are never back-tested.
"""

import json


def match_key(home, away, date_iso):
    """Stable identity for a fixture across rebuilds."""
    return f"{home}|{away}|{date_iso or ''}"


def load_log(path):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return []
    return []


def save_log(path, log):
    path.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")


def _side(hs, away_score):
    return "home" if hs > away_score else "away" if away_score > hs else "draw"


def record_predictions(log, upcoming, now_iso):
    """Add a pre-match record for each newly-predicted upcoming fixture."""
    have = {r["key"] for r in log}
    for m in upcoming:
        pred = m.get("prediction")
        if not pred:
            continue
        key = match_key(m["home"], m["away"], m.get("date_iso"))
        if key in have:
            continue
        pick = pred.get("prediction")
        side = "home" if pick == m["home"] else "away" if pick == m["away"] else "draw"
        log.append({
            "key": key, "home": m["home"], "away": m["away"],
            "date_iso": m.get("date_iso"), "stage": m.get("stage"),
            "predicted_team": pick, "predicted_side": side,
            "confidence": pred.get("confidence"),
            "made_at": now_iso, "resolved": False,
        })
        have.add(key)
    return log


def resolve(log, matches, now_iso):
    """Resolve any unresolved log entry whose match has now finished."""
    by_key = {match_key(m["home"], m["away"], m.get("date_iso")): m for m in matches}
    for r in log:
        if r.get("resolved"):
            continue
        m = by_key.get(r["key"])
        if m and m.get("played") and m.get("home_score") is not None:
            hs, as_ = m["home_score"], m["away_score"]
            # In a knockout decided by ET/penalties, judge by who advanced.
            w = m.get("winner")
            if w == m["home"]:
                actual = "home"
            elif w == m["away"]:
                actual = "away"
            else:
                actual = _side(hs, as_)
            r.update({
                "actual_home": hs, "actual_away": as_, "actual_side": actual,
                "actual_winner": (m["home"] if actual == "home"
                                  else m["away"] if actual == "away" else "Draw"),
                "pens": m.get("pens"),
                "correct": r["predicted_side"] == actual,
                "resolved": True, "resolved_at": now_iso,
            })
    return log


def verdicts_by_key(log):
    """Map of key -> resolved record, for embedding verdicts on match cards."""
    return {r["key"]: r for r in log if r.get("resolved")}


def accuracy(log):
    """Forward-only accuracy over resolved predictions."""
    resolved = [r for r in log if r.get("resolved")]
    correct = sum(1 for r in resolved if r.get("correct"))
    n = len(resolved)
    return {"resolved": n, "correct": correct, "pct": round(100 * correct / n) if n else 0}
