"""
Capture-once store for finished-match highlight videos.

Goals + venue/attendance/referee are parsed cheaply from Wikipedia on every
build (they're on the match object), so they don't need persisting. The one
EXPENSIVE bit is the TheSportsDB highlight video (`strVideo`), which requires a
per-match lookup — so we resolve it and persist it in `match_events.json`
(committed back by the Action).

Store entry per match:
  * a found video is stored as `{"video": <url>}` and never looked up again;
  * a not-yet-available video is stored as `{"video": null, "tries": N}` and
    RE-CHECKED on later builds (self-heals when TheSportsDB uploads it), until
    it's found or we give up after MAX_TRIES attempts.
A lookup that FAILS (rate-limit / network) is left unrecorded so a later build
retries it — we never poison the store with a false `null`. Requests are
throttled to stay under the free-tier rate limit.
"""

import json
import time
import urllib.parse

from core.http import fetch_json
from core.logger import get_logger

log = get_logger("match_events")

SDB = "https://www.thesportsdb.com/api/v1/json/3"
CAP_PER_BUILD = 12       # resolve/re-check at most this many matches per build
MAX_TRIES = 40           # give up re-checking a missing video after this many builds
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


def _needs_lookup(rec):
    """A match still needs a (re)lookup unless we have its video or gave up."""
    if rec is None:
        return True
    if rec.get("video"):
        return False
    return rec.get("tries", 0) < MAX_TRIES


def capture(events, matches):
    """Resolve / re-check up to CAP_PER_BUILD highlight videos; persist results.

    A found video is stored permanently; a missing one is re-checked on future
    builds (self-heals) until found or MAX_TRIES is reached. Failed lookups
    (rate-limit / network) are left unrecorded so a later build retries them.
    """
    finished = [m for m in matches if m.get("played") and not m.get("is_tbd")]
    checked = failed = found = 0
    for m in finished:
        if checked >= CAP_PER_BUILD:
            break
        key = match_key(m["home"], m["away"], m.get("date_iso"))
        rec = events.get(key)
        if not _needs_lookup(rec):
            continue
        try:
            video = _find_video(m["home"], m["away"])
        except _LookupFailed:
            failed += 1
            continue   # retry on a future build
        if video:
            events[key] = {"video": video}
            found += 1
        else:
            events[key] = {"video": None, "tries": (rec.get("tries", 0) if rec else 0) + 1}
        checked += 1
    have = sum(1 for v in events.values() if v.get("video"))
    log.info("match_events: %d looked up (+%d new videos, %d failed); %d/%d have a video",
             checked, found, failed, have, len(events))
    return events


def attach(events, matches):
    """Set m['video'] on each finished match from the captured store."""
    for m in matches:
        rec = events.get(match_key(m["home"], m["away"], m.get("date_iso")))
        if rec:
            m["video"] = rec.get("video")
