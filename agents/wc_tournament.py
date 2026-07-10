"""
Whole-tournament scraper.

Builds a complete picture of World Cup 2026:
  * every group-stage match (from the 12 per-group articles),
  * every knockout match (from the knockout-stage article),
  * all 12 group standings tables (from the main article).

All kick-offs are converted to London time. TBD knockout pairings are kept
(flagged is_tbd) so the bracket can still show the tournament's shape.
"""

import re
import string

from config import WIKI_BASE, WORLD_CUP_2026_KO_WIKI, WORLD_CUP_2026_WIKI
from core.http import fetch_soup
from core.logger import get_logger
from core.timeutil import london_label, to_london

log = get_logger("wc_tournament")

STAGES_ORDER = [
    "Group stage", "Round of 32", "Round of 16", "Quarter-finals",
    "Semi-finals", "Third place play-off", "Final",
]

_SCORE_RE = re.compile(r"(\d+)\s*[-–−]\s*(\d+)")
_ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_PLACEHOLDER_RE = re.compile(
    r"\b(winner|winners|runner|runners|loser|losers|tbd|match|group|place|"
    r"third|second|first)\b|\d", re.IGNORECASE)
_ROUND_RE = re.compile(
    r"(Round of \d+|Quarter-?finals?|Semi-?finals?|Third[- ]place|Final)",
    re.IGNORECASE)


def _clean(t):
    return re.sub(r"\s+", " ", (t or "")).strip()


def _is_real_team(name):
    return bool(name) and len(name) >= 3 and not _PLACEHOLDER_RE.search(name)


def build_tournament():
    """Scrape and return the full tournament dict (or an empty shell)."""
    group_matches, groups = _scrape_groups()
    matches = group_matches + _scrape_knockout_matches()

    # Stable ids + sort chronologically.
    matches.sort(key=lambda m: (m.get("kickoff_iso") or "9999", m.get("stage_order", 99)))
    for i, m in enumerate(matches, 1):
        m["match_id"] = f"M{i:03d}"

    log.info("Tournament: %d matches, %d groups", len(matches), len(groups))
    return {
        "stages_order": STAGES_ORDER,
        "groups": groups,
        "matches": matches,
    }


# --------------------------------------------------------------------------- #
# Matches
# --------------------------------------------------------------------------- #
def _scrape_groups():
    """Fetch each group page once; return (matches, standings) together."""
    matches, groups = [], []
    for letter in string.ascii_uppercase[:12]:            # Groups A–L
        url = f"{WIKI_BASE}/wiki/2026_FIFA_World_Cup_Group_{letter}"
        soup = fetch_soup(url)
        if soup is None:
            log.warning("Group %s page unavailable", letter)
            continue
        for box in soup.select("div.footballbox"):
            m = _parse_box(box, stage="Group stage", group=f"Group {letter}")
            if m:
                matches.append(m)
        standings = _standings_from_page(soup)
        if standings:
            groups.append({"name": f"Group {letter}", "standings": standings})
    log.info("Scraped %d group matches, %d group tables", len(matches), len(groups))
    return matches, groups


def _standings_from_page(soup):
    for tbl in soup.select("table.wikitable"):
        header = tbl.find("tr")
        if not header:
            continue
        htext = header.get_text(" ", strip=True)
        if "Pld" in htext and ("Pts" in htext or "Points" in htext):
            rows = _parse_standings(tbl)
            if rows:
                return rows
    return None


def _scrape_knockout_matches():
    soup = fetch_soup(WORLD_CUP_2026_KO_WIKI)
    if soup is None:
        log.error("Knockout page unavailable")
        return []
    out = []
    for box in soup.select("div.footballbox"):
        stage = _nearest_round(box)
        m = _parse_box(box, stage=stage, group=None)
        if m:
            out.append(m)
    log.info("Scraped %d knockout matches", len(out))
    return out


def _parse_box(box, stage, group):
    home_el = box.select_one(".fhome")
    away_el = box.select_one(".faway")
    if not (home_el and away_el):
        return None
    home = _clean(home_el.get_text())
    away = _clean(away_el.get_text())
    if not home or not away:
        return None

    score_el = box.select_one(".fscore")
    score_txt = _clean(score_el.get_text()) if score_el else ""
    sm = _SCORE_RE.search(score_txt)
    played = bool(sm)

    date_el = box.select_one(".dtstart") or box.select_one(".fdate")
    date_iso = ""
    if date_el:
        dm = _ISO_RE.search(date_el.get_text())
        date_iso = dm.group() if dm else ""

    time_el = box.select_one(".ftime")
    time_raw = _clean(time_el.get_text()) if time_el else ""

    venue, city, attendance, referee = _parse_match_info(box.select_one(".fright"))
    goals = _parse_goals(box) if played else []
    london_dt, kickoff_iso = to_london(date_iso, time_raw)
    is_tbd = not (_is_real_team(home) and _is_real_team(away))

    hs = int(sm.group(1)) if sm else None
    aws = int(sm.group(2)) if sm else None

    # Extra time / penalty shootout (knockout matches). Wikipedia keeps the
    # shootout aggregate in the box text as "Penalties ... 3–4 ...".
    aet = "a.e.t" in score_txt.lower()
    pens = _parse_penalties(box)

    # Who actually advanced.
    winner = None
    if played:
        if hs > aws:
            winner = home
        elif aws > hs:
            winner = away
        elif pens:
            winner = home if pens["home"] > pens["away"] else away

    return {
        "stage": stage,
        "stage_order": STAGES_ORDER.index(stage) if stage in STAGES_ORDER else 99,
        "group": group,
        "date_iso": date_iso,
        "kickoff_iso": kickoff_iso,
        "kickoff_london": london_label(date_iso, time_raw, with_time=True),
        "date_london": london_label(date_iso, time_raw, with_time=False),
        "venue": venue,
        "city": city,
        "home": home,
        "away": away,
        "home_score": hs,
        "away_score": aws,
        "aet": aet,
        "pens": pens,          # {"home": int, "away": int} or None
        "winner": winner,      # advancing team, or None for a true draw
        "attendance": attendance,
        "referee": referee,
        "goals": goals,        # [{team:'home'/'away', player, minute}] sorted by minute
        "played": played,
        "is_tbd": is_tbd,
    }


def _parse_goals(box):
    """Scorer + minute per goal from the '.fhgoal'/'.fagoal' cells."""
    goals = []
    for side, sel in (("home", ".fhgoal"), ("away", ".fagoal")):
        cell = box.select_one(sel)
        if not cell:
            continue
        for li in (cell.select("li") or [cell]):
            t = _clean(li.get_text(" "))
            if not t:
                continue
            player = re.sub(r"\s*\d+(?:\+\d+)?['′].*$", "", t).strip()
            player = re.sub(r"\s*\(.*?\)\s*$", "", player).strip()
            if not player:
                continue
            for mn in re.findall(r"(\d+)(?:\+\d+)?['′]", t):
                goals.append({"team": side, "player": player, "minute": int(mn)})
    goals.sort(key=lambda g: g["minute"])
    return goals


def _parse_penalties(box):
    """Return {'home': X, 'away': Y} from a shootout, or None if there wasn't one."""
    text = _clean(box.get_text(" "))
    m = re.search(r"Penalt(?:y|ies)\b(.*)", text, re.IGNORECASE)
    if not m:
        return None
    ms = _SCORE_RE.search(m.group(1))
    if not ms:
        return None
    return {"home": int(ms.group(1)), "away": int(ms.group(2))}


def _parse_match_info(right_el):
    """Return (venue, city, attendance, referee) from the '.fright' block."""
    if right_el is None:
        return "", "", None, None
    text = _clean(right_el.get_text(" "))
    att = re.search(r"Attendance:\s*([\d,]+)", text)
    ref = re.search(r"Referee:\s*(.+)$", text)
    referee = None
    if ref:
        referee = re.sub(r"\s*\)", ")", re.sub(r"\(\s*", "(", ref.group(1).strip()))
    head = re.split(r"\bAttendance\b|\bReferee\b", text)[0].strip()
    parts = [p.strip() for p in head.split(",", 1)] if head else [""]
    venue = parts[0]
    city = parts[1] if len(parts) > 1 else ""
    return venue, city, (att.group(1) if att else None), referee


def _nearest_round(box):
    for h in box.find_all_previous(["h2", "h3", "h4"]):
        m = _ROUND_RE.search(_clean(h.get_text()))
        if m:
            name = m.group(0).lower()
            if "third" in name and "place" in name:
                return "Third place play-off"
            # Normalise to our canonical stage labels (canonical-in-name only).
            for stage in STAGES_ORDER:
                key = stage.lower().replace("-", "").replace(" ", "")
                if key in name.replace("-", "").replace(" ", ""):
                    return stage
            return m.group(0)
    return "Knockout"


# --------------------------------------------------------------------------- #
# Standings — parsed by header column position (robust to +/−/footnotes)
# --------------------------------------------------------------------------- #
def _num(text):
    """Extract a signed integer from a messy cell like '+5', '− 1', '4 [a]'."""
    t = (text or "").replace("−", "-").replace("–", "-").replace(" ", "")
    m = re.search(r"-?\d+", t)
    return int(m.group()) if m else None


def _parse_standings(tbl):
    header = tbl.find("tr")
    labels = [_clean(c.get_text(" ")) for c in header.find_all(["th", "td"])]

    def col(*names):
        for i, lab in enumerate(labels):
            low = lab.lower()
            if any(low == n or low.startswith(n) for n in names):
                return i
        return None

    idx = {k: col(*v) for k, v in {
        "team": ("team",), "pld": ("pld", "played"), "w": ("w",), "d": ("d",),
        "l": ("l",), "gf": ("gf",), "ga": ("ga",), "pts": ("pts", "points"),
    }.items()}
    if idx["team"] is None or idx["pts"] is None or idx["pld"] is None:
        return []

    rows = []
    for tr in tbl.select("tr")[1:]:
        cells = tr.find_all(["td", "th"])
        if len(cells) <= idx["pts"]:
            continue
        texts = [_clean(c.get_text(" ")) for c in cells]
        raw = re.sub(r"\[.*?\]", "", texts[idx["team"]]).strip()
        host = bool(re.search(r"\(H\)", raw, re.IGNORECASE))
        team = re.sub(r"\s*\(H\)", "", raw, flags=re.IGNORECASE).strip()
        if not _is_real_team(team):
            continue
        vals = {k: _num(texts[i]) for k, i in idx.items() if k != "team" and i is not None}
        if vals.get("pld") is None or vals.get("pts") is None:
            continue
        gf, ga = vals.get("gf") or 0, vals.get("ga") or 0
        rows.append({"team": team, "host": host, "pld": vals["pld"],
                     "w": vals.get("w") or 0, "d": vals.get("d") or 0,
                     "l": vals.get("l") or 0, "gf": gf, "ga": ga,
                     "gd": gf - ga, "pts": vals["pts"]})
    return rows
