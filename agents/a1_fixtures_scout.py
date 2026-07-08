"""
Agent 1 — Fixtures Scout.

Responsibility: produce the next `NUM_FIXTURES` upcoming World Cup 2026
matches with date, time, teams, venue and stage.

Strategy (Wikipedia-first):
  1. Fetch the 2026 FIFA World Cup Wikipedia article.
  2. Parse `div.footballbox` match blocks — Wikipedia's standard match template
     that carries date, both teams, score (if played) and venue.
  3. Keep matches that are unplayed / in the future and take the first N.
  4. If scraping yields nothing usable, fall back to the bundled sample set.

Never raises on a bad source — it degrades to sample data instead.
"""

import re
from datetime import datetime

from agents.base import BaseAgent
from agents.sample_data import SAMPLE_FIXTURES
from config import FIXTURES_JSON, NUM_FIXTURES, WORLD_CUP_2026_WIKI
from core.http import fetch_soup
from core.storage import save_json

# Clean ISO date embedded by Wikipedia's dtstart microformat.
_ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
# Words that mark a placeholder / not-yet-decided team (e.g. "Winner Match 97").
_PLACEHOLDER_RE = re.compile(
    r"\b(winner|winners|runner|runners|loser|losers|tbd|match|group)\b|\d",
    re.IGNORECASE,
)


class FixturesScout(BaseAgent):
    name = "fixtures_scout"

    def run(self, **kwargs):
        fixtures = self._scrape_wikipedia()

        if fixtures:
            self.log.info("Scraped %d live fixture(s) from Wikipedia", len(fixtures))
            source = "wikipedia"
        else:
            self.log.warning("No live fixtures found — falling back to SAMPLE DATA")
            fixtures = [dict(f) for f in SAMPLE_FIXTURES[:NUM_FIXTURES]]
            source = "sample"

        payload = {
            "source": source,
            "is_sample": source == "sample",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "count": len(fixtures),
            "fixtures": fixtures,
        }
        save_json(FIXTURES_JSON, payload)
        return payload

    # ------------------------------------------------------------------ #
    # Scraping
    # ------------------------------------------------------------------ #
    def _scrape_wikipedia(self):
        soup = fetch_soup(WORLD_CUP_2026_WIKI)
        if soup is None:
            self.log.error("Could not fetch WC2026 Wikipedia page")
            return []

        boxes = soup.select("div.footballbox")
        self.log.debug("Found %d footballbox blocks", len(boxes))

        parsed = []
        for box in boxes:
            fx = self._parse_footballbox(box)
            if fx:
                parsed.append(fx)

        upcoming = self._select_upcoming(parsed)
        return upcoming[:NUM_FIXTURES]

    def _parse_footballbox(self, box):
        """Extract one fixture dict from a footballbox, or None if unusable."""
        try:
            home_el = box.select_one(".fhome")
            away_el = box.select_one(".faway")
            score_el = box.select_one(".fscore")
            time_el = box.select_one(".ftime")
            right_el = box.select_one(".fright")

            if not (home_el and away_el):
                return None

            home = self._clean(home_el.get_text())
            away = self._clean(away_el.get_text())
            if not (self._is_real_team(home) and self._is_real_team(away)):
                return None

            score_txt = self._clean(score_el.get_text()) if score_el else ""
            played = bool(re.search(r"\d+\s*[-–−]\s*\d+", score_txt))

            # dtstart carries a clean ISO date; fall back to any ISO in .fdate.
            date_el = box.select_one(".dtstart") or box.select_one(".fdate")
            parsed_date = self._parse_date(date_el.get_text() if date_el else "")

            venue, city = self._parse_venue(right_el)
            time_txt = self._clean_time(time_el.get_text() if time_el else "")

            return {
                "match_id": None,
                "stage": self._nearest_stage(box),
                "date": parsed_date.isoformat() if parsed_date else "",
                "time": time_txt,
                "home": home,
                "away": away,
                "venue": venue,
                "city": city,
                "played": played,
                "_sort_date": parsed_date,
                "is_sample": False,
            }
        except Exception as exc:  # noqa: BLE001
            self.log.debug("Skipped a footballbox: %s", exc)
            return None

    def _select_upcoming(self, fixtures):
        """Prefer future/unplayed matches, sorted chronologically."""
        today = datetime.now().date()

        def is_future(fx):
            d = fx.get("_sort_date")
            if d is None:
                return not fx.get("played")
            return d >= today

        future = [f for f in fixtures if is_future(f)]
        pool = future or fixtures
        pool.sort(key=lambda f: (f.get("_sort_date") or today))

        # Strip the internal sort key before returning.
        for f in pool:
            f.pop("_sort_date", None)
        # Assign stable ids.
        for i, f in enumerate(pool, 1):
            f["match_id"] = f"WC-{i}"
        return pool

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _clean(text):
        return re.sub(r"\s+", " ", (text or "")).strip()

    @staticmethod
    def _is_real_team(name):
        """Reject placeholders like 'Winner Match 97' / 'Runners-up Group A'."""
        if not name or len(name) < 3:
            return False
        return not _PLACEHOLDER_RE.search(name)

    @staticmethod
    def _parse_date(text):
        """Pull the embedded ISO date (YYYY-MM-DD) from a date cell."""
        m = _ISO_RE.search(text or "")
        if not m:
            return None
        try:
            return datetime.strptime(m.group(), "%Y-%m-%d").date()
        except ValueError:
            return None

    def _parse_venue(self, right_el):
        """From '.fright' text, split out venue and city.

        Example: 'SoFi Stadium , Inglewood Attendance: 69,237 Referee: ...'
        -> ('SoFi Stadium', 'Inglewood')
        """
        if right_el is None:
            return "", ""
        text = self._clean(right_el.get_text(" "))
        # Drop everything from Attendance/Referee onwards.
        text = re.split(r"\bAttendance\b|\bReferee\b", text)[0].strip()
        if not text:
            return "", ""
        parts = [p.strip() for p in text.split(",", 1)]
        venue = parts[0]
        city = parts[1] if len(parts) > 1 else ""
        return venue, city

    def _clean_time(self, text):
        """Normalise '12:00p.m.UTC−7' into '12:00 p.m. UTC-7'."""
        if not text:
            return ""
        text = text.replace("−", "-")
        text = re.sub(r"(a\.m\.|p\.m\.)", r" \1 ", text)
        text = text.replace("UTC", " UTC")
        return self._clean(text)

    def _nearest_stage(self, box):
        """Derive the round name from the nearest preceding heading."""
        heading = box.find_previous(["h2", "h3", "h4"])
        if heading is None:
            return ""
        text = self._clean(heading.get_text())
        return re.sub(r"\[edit\]", "", text).strip()


def run(**kwargs):
    """Module-level convenience entry point used by the orchestrator."""
    return FixturesScout().execute(**kwargs)
