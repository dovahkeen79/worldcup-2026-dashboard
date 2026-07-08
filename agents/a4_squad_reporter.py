"""
Agent 4 — Squad Reporter  (Phase 1, runs in parallel with Agents 2 & 3).

For each team in the fixtures, report:
  * key_players — surfaced from the real squad table (top scorers + most-capped),
  * coach       — scraped from the squad section's "Coach:" line,
  * formation   — expected formation (from bundled data where known; the squads
                  page doesn't carry it, so flagged 'not reported' otherwise),
  * injuries    — from bundled data where known, else flagged 'not reported'.

Primary source: the '2026 FIFA World Cup squads' Wikipedia article.
Degrades gracefully per-team if the section can't be found.
"""

import re

from agents.base import BaseAgent
from agents.sample_data import SAMPLE_SQUADS
from config import FIXTURES_JSON, SQUADS_JSON, WORLD_CUP_2026_SQUADS_WIKI
from core.http import fetch_soup
from core.storage import load_json, save_json


class SquadReporter(BaseAgent):
    name = "squad_reporter"

    def run(self, fixtures=None, **kwargs):
        fixtures = fixtures or self._load_fixtures()
        teams = self._teams_from_fixtures(fixtures)
        self.log.info("Reporting squads for %d team(s)", len(teams))

        soup = fetch_soup(WORLD_CUP_2026_SQUADS_WIKI)
        if soup is None:
            self.log.warning("Squads page unavailable — using SAMPLE squads only")

        squads = {}
        for team in teams:
            squads[team] = self._squad_for(team, soup)

        payload = {"teams": squads}
        save_json(SQUADS_JSON, payload)
        return payload

    # ------------------------------------------------------------------ #
    def _squad_for(self, team, soup):
        sample = SAMPLE_SQUADS.get(team, {})
        scraped = self._scrape_squad(team, soup) if soup is not None else None

        if scraped:
            return {
                "status": "ok",
                "source": "wikipedia",
                "coach": scraped["coach"] or sample.get("manager", "Unknown"),
                "key_players": scraped["key_players"],
                "squad_size": scraped["squad_size"],
                # These aren't on the squads page — use bundled data if we have it.
                "formation": sample.get("formation", "Not reported"),
                "injuries": sample.get("injuries", []),
                "notes": None if sample else "formation/injuries not reported for this team",
            }

        if sample:
            self.log.warning("No scraped squad for %s — using SAMPLE squad", team)
            return {
                "status": "sample", "source": "sample",
                "coach": sample.get("manager", "Unknown"),
                "key_players": [{"name": p} for p in sample.get("key_players", [])],
                "squad_size": None,
                "formation": sample.get("formation", "Not reported"),
                "injuries": sample.get("injuries", []),
                "notes": "sample squad data",
            }

        self.log.warning("No squad data for %s", team)
        return self.degraded(f"no squad section found for {team}",
                             coach="Unknown", key_players=[], squad_size=None,
                             formation="Not reported", injuries=[])

    def _scrape_squad(self, team, soup):
        heading = self._find_team_heading(team, soup)
        if heading is None:
            return None
        table = heading.find_next("table")
        if table is None:
            return None

        players = self._parse_players(table)
        if not players:
            return None

        return {
            "coach": self._find_coach(heading),
            "key_players": self._pick_key_players(players),
            "squad_size": len(players),
        }

    @staticmethod
    def _find_team_heading(team, soup):
        for h in soup.find_all(["h3", "h4"]):
            text = re.sub(r"\[edit\]", "", h.get_text(" ", strip=True)).strip()
            if text == team:
                return h
        return None

    @staticmethod
    def _parse_players(table):
        players = []
        for tr in table.select("tr"):
            cells = tr.find_all(["td", "th"])
            if len(cells) < 6:
                continue
            pos = _clean_pos(cells[1].get_text(" ", strip=True))
            raw_name = cells[2].get_text(" ", strip=True)
            if not raw_name or pos.lower() in ("pos.", "pos"):
                continue
            name, is_captain = _clean_player_name(raw_name)
            caps = _first_int(cells[4].get_text())
            goals = _first_int(cells[5].get_text())
            players.append({"name": name, "pos": pos, "caps": caps,
                            "goals": goals, "captain": is_captain})
        return players

    @staticmethod
    def _pick_key_players(players):
        """Blend top scorers and most-capped players into a key-player list."""
        top_scorers = sorted(players, key=lambda p: p["goals"], reverse=True)[:3]
        most_capped = sorted(players, key=lambda p: p["caps"], reverse=True)[:2]
        seen, key = set(), []
        for p in top_scorers + most_capped:
            if p["name"] in seen:
                continue
            seen.add(p["name"])
            key.append({"name": p["name"], "pos": p["pos"], "caps": p["caps"],
                        "goals": p["goals"], "captain": p.get("captain", False)})
            if len(key) >= 4:
                break
        return key

    @staticmethod
    def _find_coach(heading):
        node = heading.find_next(string=re.compile(r"Coach", re.IGNORECASE))
        if node is None:
            return None
        text = re.sub(r"\s+", " ", node.parent.get_text(" ", strip=True))
        m = re.search(r"Coach:?\s*(.+)", text, re.IGNORECASE)
        return m.group(1).strip() if m else None

    # ------------------------------------------------------------------ #
    @staticmethod
    def _teams_from_fixtures(fixtures):
        teams = []
        for fx in fixtures:
            for side in ("home", "away"):
                if fx.get(side) and fx[side] not in teams:
                    teams.append(fx[side])
        return teams

    @staticmethod
    def _load_fixtures():
        data = load_json(FIXTURES_JSON, default={"fixtures": []})
        return data.get("fixtures", [])


def _first_int(text):
    m = re.search(r"\d+", text or "")
    return int(m.group()) if m else 0


def _clean_pos(raw):
    """Extract the GK/DF/MF/FW token, dropping Wikipedia's numeric sort-key."""
    m = re.search(r"\b(GK|DF|MF|FW)\b", raw or "", re.IGNORECASE)
    return m.group(1).upper() if m else (raw or "").strip()


def _clean_player_name(raw):
    """Strip the '(captain)' marker and footnotes; return (name, is_captain)."""
    is_captain = bool(re.search(r"\bcaptain\b", raw, re.IGNORECASE))
    # Remove any parenthetical (captain), footnote brackets, and extra spaces.
    name = re.sub(r"\(.*?\)|\[.*?\]", "", raw)
    name = re.sub(r"\s+", " ", name).strip()
    return name, is_captain


def run(**kwargs):
    return SquadReporter().execute(**kwargs)
