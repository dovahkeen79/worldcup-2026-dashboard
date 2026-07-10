"""
Capture-once store for finished-match highlight videos.

Goals + venue/attendance/referee are parsed cheaply from Wikipedia on every
build (they're on the match object), so they don't need persisting. The one
EXPENSIVE bit is the TheSportsDB highlight video (`strVideo`), which requires a
per-match lookup — so we resolve it ONCE per finished match and persist it in
`match_events.json` (committed back by the Action), never re-fetching.

A match is only marked `video_checked` when TheSportsDB actually ANSWERED
(whether or not it had a video). If the lookup fails (rate-limit / network),
the match is left unchecked so a later build retries it — we never poison the
store with a false `null`. Requests are throttled to stay under the free-tier
rate limit.
"""

import json
import time
import urllib.parse

from core.http import fetch_json
from core.logger import get_logger

log = get_logger("match_events")

SDB = "https://www.thesportsdb.com/api/v1/json/3"
CAP_PER_BUILD = 12       # resolve at most this many new videos per build (polite backfill)
_MIN_INTERVAL = 2.0      # seconds between SDB calls (free tier rate-limits hard)

# The few WC2026 teams whose TheSportsDB event name differs from the Wikipedia
# name we scrape. searchevents matches on the event's own naming.
_EVENT_ALIASES = {
    "United States": "USA",
    "Bosnia and Herzegovina": "Bosnia-Herzegovina",
}

_last_call = [0.0]


class _LookupFailed(Exception):
    """The API didn't answer (rate-limit / network) — retry later, don't record."""


def match_key(home, away, date_iso):
    return f"{home}|{away}|{date_iso or ''}"


def load(path):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return {}
    return {}


def save(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _get(url):
    """Throttled TheSportsDB GET. Returns parsed JSON, or None if it failed."""
    wait = _MIN_INTERVAL - (time.monotonic() - _last_call[0])
    if wait > 0:
        time.sleep(wait)
    data = fetch_json(url)
    _last_call[0] = time.monotonic()
    return data


def _find_video(home, away):
    """A finished WC2026 match's highlight URL from TheSportsDB, or None.

    Uses searchevents by name, which reliably returns the exact match + its
    `strVideo`. Raises _LookupFailed if the API didn't answer, so the match is
    retried on a later build.
    """
    h = _EVENT_ALIASES.get(home, home)
    a = _EVENT_ALIASES.get(away, away)
    for hh, aa in ((h, a), (a, h)):   # event name should be home_vs_away, but be safe
        q = urllib.parse.quote(f"{hh}_vs_{aa}".replace(" ", "_"))
        data = _get(f"{SDB}/searchevents.php?e={q}")
        if data is None:
            raise _LookupFailed(f"searchevents {hh} v {aa}")
        for e in data.get("event") or []:
            if e.get("strSeason") == "2026":
                return e.get("strVideo") or None
    return None


def capture(events, matches):
    """Resolve up to CAP_PER_BUILD new highlight videos; persist permanently.

    Failed lookups are left unrecorded so a later build retries them.
    """
    finished = [m for m in matches if m.get("played") and not m.get("is_tbd")]
    checked = failed = 0
    for m in finished:
        if checked >= CAP_PER_BUILD:
            break
        key = match_key(m["home"], m["away"], m.get("date_iso"))
        if events.get(key, {}).get("video_checked"):
            continue
        try:
            video = _find_video(m["home"], m["away"])
        except _LookupFailed:
            failed += 1
            continue   # retry on a future build
        events[key] = {"video": video, "video_checked": True}
        checked += 1
    have = sum(1 for v in events.values() if v.get("video"))
    log.info("match_events: +%d checked (%d failed, retry later); %d/%d have a video",
             checked, failed, have, len(events))
    return events


def attach(events, matches):
    """Set m['video'] on each finished match from the captured store."""
    for m in matches:
        rec = events.get(match_key(m["home"], m["away"], m.get("date_iso")))
        if rec:
            m["video"] = rec.get("video")
