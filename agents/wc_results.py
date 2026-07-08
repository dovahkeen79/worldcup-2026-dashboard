"""
Shared helper: parse every *played* match from the 2026 World Cup Wikipedia
article's footballbox blocks.

Agents 2 (Form) and 3 (H2H) both need the tournament's completed results, so
the parsing lives here once. Returns a list of normalised result dicts.
"""

import re

from config import WORLD_CUP_2026_KO_WIKI, WORLD_CUP_2026_WIKI
from core.http import fetch_soup
from core.logger import get_logger

log = get_logger("wc_results")

# Pages to mine, in order. The dedicated knockout article carries the fullest
# set of completed footballboxes; the main article backfills anything else.
# (The group-stage results live in transcluded sub-pages that aren't scraped
# as footballboxes, so recent form is knockout-round deep.)
_RESULT_PAGES = (WORLD_CUP_2026_KO_WIKI, WORLD_CUP_2026_WIKI)

# Recognised round names, matched against preceding headings to label a match.
_ROUND_RE = re.compile(
    r"(Round of \d+|Quarter-?finals?|Semi-?finals?|Third[- ]place|Final|Group [A-L])",
    re.IGNORECASE,
)

# Module-level cache so the parallel agents don't each re-fetch the same pages.
_CACHE = None

_SCORE_RE = re.compile(r"(\d+)\s*[-–−]\s*(\d+)")
_ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_PLACEHOLDER_RE = re.compile(
    r"\b(winner|winners|runner|runners|loser|losers|tbd|match|group)\b|\d",
    re.IGNORECASE,
)


def _clean(text):
    return re.sub(r"\s+", " ", (text or "")).strip()


def _is_real_team(name):
    return bool(name) and len(name) >= 3 and not _PLACEHOLDER_RE.search(name)


def _nearest_round(box):
    """Walk preceding headings and return the first recognised round name."""
    for heading in box.find_all_previous(["h2", "h3", "h4"]):
        m = _ROUND_RE.search(_clean(heading.get_text()))
        if m:
            return m.group(0)
    return "World Cup"


def _parse_page(soup):
    """Parse all completed footballbox matches from one page's soup."""
    out = []
    for box in soup.select("div.footballbox"):
        home_el = box.select_one(".fhome")
        away_el = box.select_one(".faway")
        score_el = box.select_one(".fscore")
        if not (home_el and away_el and score_el):
            continue

        home = _clean(home_el.get_text())
        away = _clean(away_el.get_text())
        if not (_is_real_team(home) and _is_real_team(away)):
            continue

        m = _SCORE_RE.search(_clean(score_el.get_text()))
        if not m:
            continue  # unplayed fixture — skip

        date_el = box.select_one(".dtstart") or box.select_one(".fdate")
        date_m = _ISO_RE.search(date_el.get_text() if date_el else "")
        stage = _nearest_round(box)

        out.append({
            "date": date_m.group() if date_m else "",
            "home": home,
            "away": away,
            "home_score": int(m.group(1)),
            "away_score": int(m.group(2)),
            "stage": stage,
        })
    return out


def parse_played_matches():
    """Return all completed WC2026 matches across the mined pages (deduped).

    Each item: {date, home, away, home_score, away_score, stage}.
    Result is cached for the process so parallel agents share one fetch set.
    """
    global _CACHE
    if _CACHE is not None:
        return _CACHE

    seen = set()
    results = []
    for url in _RESULT_PAGES:
        soup = fetch_soup(url)
        if soup is None:
            log.warning("Result page unavailable: %s", url)
            continue
        for r in _parse_page(soup):
            key = (r["date"], r["home"], r["away"], r["home_score"], r["away_score"])
            if key in seen:
                continue
            seen.add(key)
            results.append(r)

    log.info("Parsed %d unique played matches across %d page(s)",
             len(results), len(_RESULT_PAGES))
    _CACHE = results
    return results
