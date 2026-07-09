"""
Top-scorers scraper (one page fetch).

Parses the "Goalscorers" section of the 2026 FIFA World Cup Wikipedia article.
The section is grouped by goal count:

    <p>8 goals</p>
    <ul><li>[flag] Lionel Messi</li> ...</ul>
    <p>7 goals</p>
    <ul>...</ul>

Each <li> carries the player name (a link) and the country (flag img alt,
e.g. "Argentina national football team"). Returns a flat, ranked list.
Degrades gracefully to [] if anything is missing.
"""

import re

from config import WORLD_CUP_2026_WIKI
from core.http import fetch_soup
from core.logger import get_logger

log = get_logger("goalscorers")

_NAT_SUFFIX = re.compile(r"\s+national football team$", re.IGNORECASE)


def fetch_top_scorers(limit=20):
    soup = fetch_soup(WORLD_CUP_2026_WIKI)
    if soup is None:
        log.warning("WC2026 page unavailable — no top scorers")
        return []

    heading = next((h for h in soup.find_all(["h2", "h3"])
                    if "goalscorer" in h.get_text().lower()), None)
    if heading is None:
        log.warning("No Goalscorers heading found")
        return []

    results, current = [], None
    node = heading
    for _ in range(400):
        node = node.find_next(["p", "ul", "h2", "h3", "h4"])
        if node is None:
            break
        if node.name in ("h2", "h3", "h4"):
            break   # reached the next section heading
        if node.name == "p":
            m = re.search(r"(\d+)\s*goals?", node.get_text(), re.IGNORECASE)
            if m:
                current = int(m.group(1))
        elif node.name == "ul" and current:
            for li in node.find_all("li", recursive=False):
                player, country = _parse_li(li)
                if player:
                    results.append({"player": player, "country": country,
                                    "goals": current})

    log.info("Parsed %d top scorers", len(results))
    return results[:limit]


def _parse_li(li):
    img = li.find("img")
    country = ""
    if img and img.get("alt"):
        country = _NAT_SUFFIX.sub("", img.get("alt")).strip()
    player = ""
    for a in li.find_all("a"):
        txt = a.get_text(strip=True)
        if txt:
            player = txt
            break
    if not player:
        player = re.sub(r"\s+", " ", li.get_text(" ", strip=True)).strip()
    return player, country
