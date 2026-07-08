"""
Universal all-time head-to-head lookup between two national teams.

The earlier approach relied on a "Head-to-head record" table that only *some*
Wikipedia national-team pages carry (France/Argentina had it; Spain/Belgium/
Norway/England did not), so many pairings came back blank.

This module fixes that with a source that has a page for EVERY pairing:
11v11.com's opposing-team record. Strategy, in order:

  1. 11v11.com  — universal, real all-time W/D/L + last meeting.
  2. Wikipedia  — the per-team H2H table, if present (either orientation).
  3. Sample     — bundled fallback for the demo teams.

All records are normalised to the *home* team's perspective.
"""

import re

from agents.sample_data import SAMPLE_H2H
from config import wiki_team_url
from core.http import fetch_soup
from core.logger import get_logger

log = get_logger("h2h")

# 11v11 uses lowercase, hyphenated slugs; a few need explicit overrides.
_SLUG_OVERRIDES = {
    "United States": "usa",
    "South Korea": "south-korea",
    "Ivory Coast": "ivory-coast",
    "DR Congo": "congo-dr",
    "Cape Verde": "cape-verde-islands",
    "Saudi Arabia": "saudi-arabia",
    "Czech Republic": "czech-republic",
}


def _slug(team):
    return _SLUG_OVERRIDES.get(team, team.lower().replace(" ", "-"))


def fetch_h2h(home, away):
    """Return an all-time record (home perspective) or None.

    Shape: {source, played, home_wins, draws, away_wins, last_meeting}
    """
    return (
        _from_11v11(home, away)
        or _from_wikipedia(home, away)
        or _from_sample(home, away)
    )


# --------------------------------------------------------------------------- #
# 1) 11v11.com — works for every pairing
# --------------------------------------------------------------------------- #
def _from_11v11(home, away):
    url = f"https://www.11v11.com/teams/{_slug(home)}/tab/opposingTeams/opposition/{_slug(away)}/"
    soup = fetch_soup(url)
    if soup is None:
        return None
    tables = soup.select("table")
    if not tables:
        return None

    summary = {}
    for tr in tables[0].select("tr"):
        cells = [re.sub(r"\s+", " ", c.get_text(" ", strip=True))
                 for c in tr.find_all(["th", "td"])]
        if len(cells) >= 2:
            label = cells[0].lower()
            num = re.search(r"\d+", cells[1])
            if not num:
                continue
            if "won" in label:
                summary["home_wins"] = int(num.group())
            elif "drawn" in label:
                summary["draws"] = int(num.group())
            elif "lost" in label:
                summary["away_wins"] = int(num.group())

    if not {"home_wins", "draws", "away_wins"} <= summary.keys():
        return None

    played = summary["home_wins"] + summary["draws"] + summary["away_wins"]
    if played == 0:
        return None

    return {
        "source": "11v11",
        "played": played,
        "home_wins": summary["home_wins"],
        "draws": summary["draws"],
        "away_wins": summary["away_wins"],
        "last_meeting": _last_meeting_11v11(tables),
    }


def _last_meeting_11v11(tables):
    """Most recent meeting from the match-list table (listed oldest-first)."""
    if len(tables) < 2:
        return None
    latest = None
    for tr in tables[1].select("tr"):
        cells = [re.sub(r"\s+", " ", c.get_text(" ", strip=True))
                 for c in tr.find_all(["td"])]
        if len(cells) >= 4 and re.search(r"\d", cells[0]):
            date, fixture, _res, score = cells[0], cells[1], cells[2], cells[3]
            comp = cells[4] if len(cells) > 4 else ""
            tail = f" ({comp})" if comp else ""
            latest = f"{date}: {fixture} {score}{tail}"  # keep overwriting -> last wins
    return latest


# --------------------------------------------------------------------------- #
# 2) Wikipedia per-team H2H table (kept as a fallback)
# --------------------------------------------------------------------------- #
def _from_wikipedia(home, away):
    row = _wiki_row(home, away)
    if row:
        played, won, drawn, lost = row
        return _wiki_record(played, won, drawn, lost)
    row = _wiki_row(away, home)
    if row:
        played, won, drawn, lost = row  # away perspective -> flip
        return _wiki_record(played, lost, drawn, won)
    return None


def _wiki_row(page_owner, opponent):
    soup = fetch_soup(wiki_team_url(page_owner))
    if soup is None:
        return None
    table = None
    for tbl in soup.select("table.wikitable"):
        header = tbl.find("tr")
        if not header:
            continue
        htext = header.get_text(" ", strip=True).lower()
        if "opponent" in htext and ("won" in htext or "win" in htext) \
                and ("played" in htext or "pld" in htext):
            table = tbl
            break
    if table is None:
        return None
    target = opponent.lower()
    for tr in table.select("tr"):
        cells = tr.find_all(["td", "th"])
        if len(cells) < 5:
            continue
        name = re.sub(r"\s+", " ", cells[0].get_text(" ", strip=True)).strip().lower()
        if name == target:
            try:
                return [int(c.get_text(strip=True)) for c in cells[1:5]]
            except ValueError:
                return None
    return None


def _wiki_record(played, home_wins, draws, away_wins):
    return {"source": "wikipedia", "played": played, "home_wins": home_wins,
            "draws": draws, "away_wins": away_wins, "last_meeting": None}


# --------------------------------------------------------------------------- #
# 3) Bundled sample fallback
# --------------------------------------------------------------------------- #
def _from_sample(home, away):
    rec = SAMPLE_H2H.get((home, away))
    flip = False
    if rec is None:
        rec = SAMPLE_H2H.get((away, home))
        flip = rec is not None
    if rec is None:
        return None
    hw = rec["away_wins"] if flip else rec["home_wins"]
    aw = rec["home_wins"] if flip else rec["away_wins"]
    return {"source": "sample", "played": rec["played"], "home_wins": hw,
            "draws": rec["draws"], "away_wins": aw,
            "last_meeting": rec.get("last_meeting")}
