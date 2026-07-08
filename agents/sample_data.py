"""
Bundled sample dataset — the graceful fallback.

If live scraping yields nothing (source down, off-season, HTML changed), the
pipeline uses these realistic-but-fictional fixtures so it always produces a
full end-to-end report. Everything here is clearly flagged `is_sample: True`
and the report renders a prominent "SAMPLE DATA" banner.
"""

# Five plausible WC2026 knockout-stage fixtures. Dates are illustrative.
SAMPLE_FIXTURES = [
    {
        "match_id": "SMP-1", "stage": "Quarter-final",
        "date": "2026-07-10", "time": "20:00",
        "home": "Argentina", "away": "France",
        "venue": "MetLife Stadium", "city": "New York/New Jersey",
        "is_sample": True,
    },
    {
        "match_id": "SMP-2", "stage": "Quarter-final",
        "date": "2026-07-10", "time": "16:00",
        "home": "Brazil", "away": "England",
        "venue": "AT&T Stadium", "city": "Dallas",
        "is_sample": True,
    },
    {
        "match_id": "SMP-3", "stage": "Quarter-final",
        "date": "2026-07-11", "time": "20:00",
        "home": "Spain", "away": "Germany",
        "venue": "SoFi Stadium", "city": "Los Angeles",
        "is_sample": True,
    },
    {
        "match_id": "SMP-4", "stage": "Quarter-final",
        "date": "2026-07-11", "time": "16:00",
        "home": "Portugal", "away": "Netherlands",
        "venue": "Estadio Azteca", "city": "Mexico City",
        "is_sample": True,
    },
    {
        "match_id": "SMP-5", "stage": "Quarter-final",
        "date": "2026-07-12", "time": "19:00",
        "home": "Mexico", "away": "Croatia",
        "venue": "BC Place", "city": "Vancouver",
        "is_sample": True,
    },
]

# Recent-form results (most recent first) for teams used in the sample fixtures.
# Each entry: opponent, result W/D/L, score, competition.
SAMPLE_FORM = {
    "Argentina": [
        {"opponent": "Ecuador", "result": "W", "score": "2-0", "comp": "WC R16"},
        {"opponent": "Australia", "result": "W", "score": "3-1", "comp": "WC Group"},
        {"opponent": "Nigeria", "result": "D", "score": "1-1", "comp": "WC Group"},
        {"opponent": "Poland", "result": "W", "score": "2-0", "comp": "WC Group"},
        {"opponent": "Chile", "result": "W", "score": "1-0", "comp": "Friendly"},
    ],
    "France": [
        {"opponent": "Senegal", "result": "W", "score": "2-1", "comp": "WC R16"},
        {"opponent": "Denmark", "result": "W", "score": "2-0", "comp": "WC Group"},
        {"opponent": "Canada", "result": "D", "score": "1-1", "comp": "WC Group"},
        {"opponent": "Tunisia", "result": "W", "score": "3-0", "comp": "WC Group"},
        {"opponent": "Germany", "result": "L", "score": "0-2", "comp": "Friendly"},
    ],
    "Brazil": [
        {"opponent": "South Korea", "result": "W", "score": "4-1", "comp": "WC R16"},
        {"opponent": "Switzerland", "result": "W", "score": "1-0", "comp": "WC Group"},
        {"opponent": "Serbia", "result": "W", "score": "2-0", "comp": "WC Group"},
        {"opponent": "Cameroon", "result": "L", "score": "0-1", "comp": "WC Group"},
        {"opponent": "Ghana", "result": "W", "score": "3-0", "comp": "Friendly"},
    ],
    "England": [
        {"opponent": "USA", "result": "W", "score": "2-1", "comp": "WC R16"},
        {"opponent": "Wales", "result": "W", "score": "3-0", "comp": "WC Group"},
        {"opponent": "Iran", "result": "W", "score": "6-2", "comp": "WC Group"},
        {"opponent": "Italy", "result": "D", "score": "1-1", "comp": "WC Group"},
        {"opponent": "Brazil", "result": "L", "score": "0-1", "comp": "Friendly"},
    ],
    "Spain": [
        {"opponent": "Morocco", "result": "W", "score": "3-2", "comp": "WC R16"},
        {"opponent": "Japan", "result": "L", "score": "1-2", "comp": "WC Group"},
        {"opponent": "Germany", "result": "D", "score": "1-1", "comp": "WC Group"},
        {"opponent": "Costa Rica", "result": "W", "score": "7-0", "comp": "WC Group"},
        {"opponent": "Portugal", "result": "W", "score": "2-1", "comp": "Nations League"},
    ],
    "Germany": [
        {"opponent": "Belgium", "result": "W", "score": "2-1", "comp": "WC R16"},
        {"opponent": "Spain", "result": "D", "score": "1-1", "comp": "WC Group"},
        {"opponent": "Japan", "result": "W", "score": "4-1", "comp": "WC Group"},
        {"opponent": "Costa Rica", "result": "W", "score": "4-2", "comp": "WC Group"},
        {"opponent": "France", "result": "W", "score": "2-0", "comp": "Friendly"},
    ],
    "Portugal": [
        {"opponent": "Switzerland", "result": "W", "score": "6-1", "comp": "WC R16"},
        {"opponent": "Uruguay", "result": "W", "score": "2-0", "comp": "WC Group"},
        {"opponent": "Ghana", "result": "W", "score": "3-2", "comp": "WC Group"},
        {"opponent": "South Korea", "result": "L", "score": "1-2", "comp": "WC Group"},
        {"opponent": "Spain", "result": "L", "score": "1-2", "comp": "Nations League"},
    ],
    "Netherlands": [
        {"opponent": "USA", "result": "W", "score": "3-1", "comp": "WC R16"},
        {"opponent": "Qatar", "result": "W", "score": "2-0", "comp": "WC Group"},
        {"opponent": "Ecuador", "result": "D", "score": "1-1", "comp": "WC Group"},
        {"opponent": "Senegal", "result": "W", "score": "2-0", "comp": "WC Group"},
        {"opponent": "Belgium", "result": "D", "score": "0-0", "comp": "Nations League"},
    ],
    "Mexico": [
        {"opponent": "Poland", "result": "W", "score": "2-1", "comp": "WC R16"},
        {"opponent": "Saudi Arabia", "result": "W", "score": "2-1", "comp": "WC Group"},
        {"opponent": "Argentina", "result": "L", "score": "0-2", "comp": "WC Group"},
        {"opponent": "Poland", "result": "D", "score": "0-0", "comp": "WC Group"},
        {"opponent": "USA", "result": "W", "score": "2-0", "comp": "Nations League"},
    ],
    "Croatia": [
        {"opponent": "Japan", "result": "W", "score": "1-1 (4-2p)", "comp": "WC R16"},
        {"opponent": "Belgium", "result": "D", "score": "0-0", "comp": "WC Group"},
        {"opponent": "Canada", "result": "W", "score": "4-1", "comp": "WC Group"},
        {"opponent": "Morocco", "result": "D", "score": "0-0", "comp": "WC Group"},
        {"opponent": "Brazil", "result": "L", "score": "1-4", "comp": "Friendly"},
    ],
}

# Head-to-head summaries (all-time) between the sample pairings.
SAMPLE_H2H = {
    ("Argentina", "France"): {"played": 12, "home_wins": 6, "draws": 3, "away_wins": 3,
                              "last_meeting": "2022-12-18 WC Final: 3-3 (Argentina won on pens)"},
    ("Brazil", "England"): {"played": 26, "home_wins": 11, "draws": 11, "away_wins": 4,
                            "last_meeting": "2017-11-14 Friendly: 0-0"},
    ("Spain", "Germany"): {"played": 26, "home_wins": 9, "draws": 8, "away_wins": 9,
                           "last_meeting": "2022-11-27 WC Group: 1-1"},
    ("Portugal", "Netherlands"): {"played": 13, "home_wins": 6, "draws": 2, "away_wins": 5,
                                  "last_meeting": "2019-06-09 Nations League Final: 1-0"},
    ("Mexico", "Croatia"): {"played": 4, "home_wins": 1, "draws": 1, "away_wins": 2,
                            "last_meeting": "2018-06-23 WC Group: 0-1"},
}

# Squad snapshots: key players, notable injuries, expected formation.
SAMPLE_SQUADS = {
    "Argentina": {"formation": "4-3-3", "key_players": ["Lionel Messi", "Julian Alvarez", "Enzo Fernandez"],
                  "injuries": ["Angel Di Maria (doubtful)"], "manager": "Lionel Scaloni"},
    "France": {"formation": "4-2-3-1", "key_players": ["Kylian Mbappe", "Aurelien Tchouameni", "William Saliba"],
               "injuries": [], "manager": "Didier Deschamps"},
    "Brazil": {"formation": "4-2-3-1", "key_players": ["Vinicius Junior", "Rodrygo", "Bruno Guimaraes"],
               "injuries": ["Neymar (out)"], "manager": "Dorival Junior"},
    "England": {"formation": "4-3-3", "key_players": ["Jude Bellingham", "Harry Kane", "Bukayo Saka"],
                "injuries": ["Luke Shaw (doubtful)"], "manager": "Thomas Tuchel"},
    "Spain": {"formation": "4-3-3", "key_players": ["Lamine Yamal", "Pedri", "Rodri"],
              "injuries": [], "manager": "Luis de la Fuente"},
    "Germany": {"formation": "4-2-3-1", "key_players": ["Jamal Musiala", "Florian Wirtz", "Kai Havertz"],
                "injuries": ["Antonio Rudiger (doubtful)"], "manager": "Julian Nagelsmann"},
    "Portugal": {"formation": "4-3-3", "key_players": ["Cristiano Ronaldo", "Bruno Fernandes", "Rafael Leao"],
                 "injuries": [], "manager": "Roberto Martinez"},
    "Netherlands": {"formation": "4-3-3", "key_players": ["Virgil van Dijk", "Cody Gakpo", "Frenkie de Jong"],
                    "injuries": ["Memphis Depay (doubtful)"], "manager": "Ronald Koeman"},
    "Mexico": {"formation": "4-3-3", "key_players": ["Santiago Gimenez", "Edson Alvarez", "Hirving Lozano"],
               "injuries": [], "manager": "Javier Aguirre"},
    "Croatia": {"formation": "4-3-3", "key_players": ["Luka Modric", "Josko Gvardiol", "Mateo Kovacic"],
                "injuries": ["Marcelo Brozovic (doubtful)"], "manager": "Zlatko Dalic"},
}
