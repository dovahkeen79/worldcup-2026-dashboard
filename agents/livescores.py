"""
Resolve TheSportsDB event ids for upcoming fixtures (build time).

The free `eventsday` feed doesn't surface World Cup matches, but each match
IS available via the team's `eventsnext` endpoint and can then be polled live
by event id (`lookupevent`). So at build time we look up the event id for each
upcoming fixture and embed it; the dashboard polls those ids live.

All network failures degrade to `None` (no live coverage for that match).
"""

import re
import urllib.parse

from core.http import fetch_json
from core.logger import get_logger

log = get_logger("livescores")

SDB = "https://www.thesportsdb.com/api/v1/json/3"

# Team name -> TheSportsDB search term, for the few that differ.
_SEARCH_ALIASES = {
    "United States": "USA",
}

_TEAM_ID_CACHE = {}


def _norm(s):
    return re.sub(r"\s+", " ", (s or "").strip()).lower()


def _team_id(name):
    if name in _TEAM_ID_CACHE:
        return _TEAM_ID_CACHE[name]
    term = _SEARCH_ALIASES.get(name, name)
    data = fetch_json(f"{SDB}/searchteams.php?t={urllib.parse.quote(term)}")
    teams = (data or {}).get("teams") or []
    tid = None
    # Prefer an exact soccer-team name match.
    for t in teams:
        if t.get("strSport") == "Soccer" and _norm(t.get("strTeam")) == _norm(term):
            tid = t.get("idTeam")
            break
    if tid is None:
        tid = next((t.get("idTeam") for t in teams if t.get("strSport") == "Soccer"), None)
    _TEAM_ID_CACHE[name] = tid
    return tid


def _resolve_event_id(home, away):
    tid = _team_id(home)
    if not tid:
        return None
    data = fetch_json(f"{SDB}/eventsnext.php?id={tid}")
    for e in (data or {}).get("events") or []:
        pair = {_norm(e.get("strHomeTeam")), _norm(e.get("strAwayTeam"))}
        if pair == {_norm(home), _norm(away)}:
            return e.get("idEvent")
    return None


def attach_event_ids(upcoming):
    """Set m['sdb_event_id'] on each upcoming fixture (None if not found)."""
    found = 0
    for m in upcoming:
        try:
            eid = _resolve_event_id(m["home"], m["away"])
        except Exception as exc:  # noqa: BLE001
            log.debug("event-id lookup failed for %s v %s: %s", m["home"], m["away"], exc)
            eid = None
        m["sdb_event_id"] = eid
        if eid:
            found += 1
    log.info("Resolved %d/%d TheSportsDB event ids", found, len(upcoming))
