"""
Agent 3 — H2H Historian  (Phase 1, runs in parallel with Agents 2 & 4).

For each fixture, produce a head-to-head picture between the two teams:

  * direct_meetings  — any completed WC2026 match where the two sides met
                       (real, from scraped results; usually none before a QF).
  * common_opponents — teams BOTH sides have faced this tournament, with each
                       side's result. A legitimate comparative signal when a
                       direct record isn't available.
  * all_time         — bundled sample all-time record for known pairings
                       (clearly flagged as sample).

Degrades gracefully: if nothing is available the record is flagged
'unavailable' and the prediction model treats H2H as no-signal.
"""

import re

from agents.base import BaseAgent
from agents.sample_data import SAMPLE_H2H
from agents.wc_results import parse_played_matches
from config import FIXTURES_JSON, H2H_JSON, wiki_team_url
from core.http import fetch_soup
from core.storage import load_json, save_json


class H2HHistorian(BaseAgent):
    name = "h2h_historian"

    def run(self, fixtures=None, **kwargs):
        fixtures = fixtures or self._load_fixtures()
        played = parse_played_matches()
        self.log.info("Computing H2H for %d fixture(s)", len(fixtures))

        h2h = {}
        for fx in fixtures:
            home, away = fx.get("home"), fx.get("away")
            if not (home and away):
                continue
            h2h[fx["match_id"]] = self._h2h_for(home, away, played)

        payload = {"matches": h2h}
        save_json(H2H_JSON, payload)
        return payload

    # ------------------------------------------------------------------ #
    def _h2h_for(self, home, away, played):
        direct = self._direct_meetings(home, away, played)
        common = self._common_opponents(home, away, played)
        all_time = self._all_time(home, away)

        has_content = bool(direct or common or all_time)
        record = {
            "home": home,
            "away": away,
            "status": "ok" if has_content else "unavailable",
            "direct_meetings": direct,
            "common_opponents": common,
            "all_time": all_time,
        }
        if not has_content:
            record["reason"] = "no direct, common-opponent, or sample data found"
            self.log.warning("No H2H content for %s vs %s", home, away)
        return record

    def _direct_meetings(self, home, away, played):
        meetings = []
        for m in played:
            teams = {m["home"], m["away"]}
            if teams == {home, away}:
                meetings.append({
                    "date": m["date"], "stage": m["stage"],
                    "score": f"{m['home']} {m['home_score']}-{m['away_score']} {m['away']}",
                })
        return meetings

    def _common_opponents(self, home, away, played):
        home_res = self._results_by_opponent(home, played)
        away_res = self._results_by_opponent(away, played)
        shared = sorted(set(home_res) & set(away_res))
        out = []
        for opp in shared:
            out.append({
                "opponent": opp,
                "home_result": home_res[opp],
                "away_result": away_res[opp],
            })
        return out

    @staticmethod
    def _results_by_opponent(team, played):
        by_opp = {}
        for m in played:
            if team == m["home"]:
                gf, ga, opp = m["home_score"], m["away_score"], m["away"]
            elif team == m["away"]:
                gf, ga, opp = m["away_score"], m["home_score"], m["home"]
            else:
                continue
            res = "W" if gf > ga else "D" if gf == ga else "L"
            by_opp[opp] = f"{res} {gf}-{ga}"
        return by_opp

    def _all_time(self, home, away):
        """All-time record. Prefer scraped Wikipedia table; fall back to sample."""
        scraped = self._scrape_all_time(home, away)
        if scraped:
            return scraped
        return self._sample_all_time(home, away)

    def _scrape_all_time(self, home, away):
        """All-time record from Wikipedia, normalised to the home perspective.

        Tries the home team's H2H table first; if that page lacks one, tries the
        away team's page and flips wins/losses. Returns None if neither works.
        """
        # Attempt 1: home team's page, opponent = away.
        row = self._scrape_from_page(home, away)
        if row:
            played, won, drawn, lost = row
            return self._record(played, home_wins=won, draws=drawn, away_wins=lost)

        # Attempt 2: away team's page, opponent = home — then flip perspective.
        row = self._scrape_from_page(away, home)
        if row:
            played, won, drawn, lost = row  # from AWAY team's perspective
            return self._record(played, home_wins=lost, draws=drawn, away_wins=won)

        return None

    def _scrape_from_page(self, page_owner, opponent):
        """Return [Played, Won, Drawn, Lost] (owner's perspective) or None."""
        url = wiki_team_url(page_owner)
        soup = fetch_soup(url)
        if soup is None:
            return None
        table = self._find_h2h_table(soup)
        if table is None:
            self.log.debug("No H2H table on %s page", page_owner)
            return None
        row = self._find_opponent_row(table, opponent)
        if row is None:
            self.log.debug("No %s row on %s page", opponent, page_owner)
            return None
        try:
            return [int(x) for x in row[:4]]
        except (ValueError, IndexError):
            return None

    @staticmethod
    def _record(played, home_wins, draws, away_wins):
        return {
            "source": "wikipedia",
            "played": played,
            "home_wins": home_wins,
            "draws": draws,
            "away_wins": away_wins,
            "last_meeting": None,
        }

    @staticmethod
    def _find_h2h_table(soup):
        """Find the wikitable whose header looks like an opponent record table."""
        for tbl in soup.select("table.wikitable"):
            header = tbl.find("tr")
            if not header:
                continue
            htext = header.get_text(" ", strip=True).lower()
            if "opponent" in htext and ("won" in htext or "win" in htext) \
                    and ("played" in htext or "pld" in htext):
                return tbl
        return None

    def _find_opponent_row(self, table, opponent):
        """Return [Played, Won, Drawn, Lost] ints for the opponent row, or None."""
        target = opponent.lower()
        for tr in table.select("tr"):
            cells = tr.find_all(["td", "th"])
            if len(cells) < 5:
                continue
            name = re.sub(r"\s+", " ", cells[0].get_text(" ", strip=True)).strip().lower()
            if name == target or (target and target in name and len(name) < len(target) + 6):
                return [c.get_text(strip=True) for c in cells[1:5]]
        return None

    @staticmethod
    def _sample_all_time(home, away):
        """Bundled all-time record fallback, normalised to fixture orientation."""
        rec = SAMPLE_H2H.get((home, away))
        flip = False
        if rec is None:
            rec = SAMPLE_H2H.get((away, home))
            flip = rec is not None
        if rec is None:
            return None
        home_wins = rec["away_wins"] if flip else rec["home_wins"]
        away_wins = rec["home_wins"] if flip else rec["away_wins"]
        return {
            "source": "sample",
            "played": rec["played"],
            "home_wins": home_wins,
            "draws": rec["draws"],
            "away_wins": away_wins,
            "last_meeting": rec["last_meeting"],
        }

    @staticmethod
    def _load_fixtures():
        data = load_json(FIXTURES_JSON, default={"fixtures": []})
        return data.get("fixtures", [])


def run(**kwargs):
    return H2HHistorian().execute(**kwargs)
