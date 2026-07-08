"""
Central configuration for the World Cup 2026 Match Analyser.

Everything tunable lives here: source URLs, HTTP behaviour, folder paths,
the prediction weights, and the curated team -> crest image map.
"""

from pathlib import Path

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
REPORTS_DIR = ROOT / "reports"
LOGS_DIR = ROOT / "logs"
TEMPLATES_DIR = ROOT / "templates"

# Ensure the working folders exist on import so no agent has to worry about it.
for _d in (DATA_DIR, REPORTS_DIR, LOGS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# JSON artefact filenames (written to DATA_DIR).
FIXTURES_JSON = "fixtures.json"
FORM_JSON = "form.json"
H2H_JSON = "h2h.json"
SQUADS_JSON = "squads.json"
ANALYSIS_JSON = "analysis.json"

# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "WorldCupAnalyser/1.0 (educational project; contact: local)"
)
REQUEST_TIMEOUT = 20          # seconds
MAX_RETRIES = 3
RETRY_BACKOFF = 1.5           # seconds, multiplied by attempt number
POLITE_DELAY = 0.5            # seconds between requests to the same host

# --------------------------------------------------------------------------- #
# Sources
# --------------------------------------------------------------------------- #
WIKI_BASE = "https://en.wikipedia.org"
WIKI_API = "https://en.wikipedia.org/w/api.php"
WORLD_CUP_2026_WIKI = "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup"
# Additional result-bearing pages mined for deeper form / H2H history.
WORLD_CUP_2026_GROUP_WIKI = "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_group_stage"
WORLD_CUP_2026_KO_WIKI = "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_knockout_stage"
# WC2026 squads page (Agent 4).
WORLD_CUP_2026_SQUADS_WIKI = "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_squads"

# How many upcoming fixtures the pipeline targets.
NUM_FIXTURES = 5
# How many recent results define a team's "form".
FORM_MATCH_COUNT = 5

# --------------------------------------------------------------------------- #
# Prediction model weights (Agent 5). Must sum to 1.0.
# --------------------------------------------------------------------------- #
WEIGHTS = {
    "form": 0.40,      # recent results
    "h2h": 0.30,       # historical head-to-head
    "squad": 0.20,     # squad availability / injuries
    "host": 0.10,      # host / home-continent advantage
}

# Host nations of WC2026 get a small edge in the "host" component.
HOST_NATIONS = {"United States", "Canada", "Mexico"}

# --------------------------------------------------------------------------- #
# Team crest map. Curated Wikipedia/Commons image URLs are the most reliable
# way to get a crest; if a team is missing we fall back to an initials badge
# rendered in the HTML. Keyed by canonical team name.
# --------------------------------------------------------------------------- #
TEAM_CRESTS = {
    "Argentina": "https://upload.wikimedia.org/wikipedia/en/thumb/c/c1/Argentina_national_football_team_logo.svg/120px-Argentina_national_football_team_logo.svg.png",
    "Brazil": "https://upload.wikimedia.org/wikipedia/en/thumb/5/5d/Brazilian_Football_Confederation_logo.svg/120px-Brazilian_Football_Confederation_logo.svg.png",
    "France": "https://upload.wikimedia.org/wikipedia/en/thumb/e/ec/France_national_football_team_seal.svg/120px-France_national_football_team_seal.svg.png",
    "England": "https://upload.wikimedia.org/wikipedia/en/thumb/1/1a/England_national_football_team_crest.svg/120px-England_national_football_team_crest.svg.png",
    "Spain": "https://upload.wikimedia.org/wikipedia/en/thumb/8/8b/Spain_national_football_team_crest.svg/120px-Spain_national_football_team_crest.svg.png",
    "Germany": "https://upload.wikimedia.org/wikipedia/en/thumb/a/ac/Germany_national_football_team_logo.svg/120px-Germany_national_football_team_logo.svg.png",
    "Portugal": "https://upload.wikimedia.org/wikipedia/en/thumb/5/5b/Portugal_national_football_team_logo.svg/120px-Portugal_national_football_team_logo.svg.png",
    "Netherlands": "https://upload.wikimedia.org/wikipedia/en/thumb/4/44/KNVB_logo.svg/120px-KNVB_logo.svg.png",
    "Belgium": "https://upload.wikimedia.org/wikipedia/en/thumb/3/39/Royal_Belgian_Football_Association_logo_2019.svg/120px-Royal_Belgian_Football_Association_logo_2019.svg.png",
    "Croatia": "https://upload.wikimedia.org/wikipedia/en/thumb/1/1b/Croatian_Football_Federation_logo.svg/120px-Croatian_Football_Federation_logo.svg.png",
    "United States": "https://upload.wikimedia.org/wikipedia/en/thumb/e/e0/United_States_Soccer_Federation_logo_2016.svg/120px-United_States_Soccer_Federation_logo_2016.svg.png",
    "Canada": "https://upload.wikimedia.org/wikipedia/en/thumb/8/8f/Canada_Soccer_logo.svg/120px-Canada_Soccer_logo.svg.png",
    "Mexico": "https://upload.wikimedia.org/wikipedia/en/thumb/9/93/Mexico_national_football_team_crest.svg/120px-Mexico_national_football_team_crest.svg.png",
    "Uruguay": "https://upload.wikimedia.org/wikipedia/en/thumb/7/70/Uruguay_national_football_team_crest.svg/120px-Uruguay_national_football_team_crest.svg.png",
    "Morocco": "https://upload.wikimedia.org/wikipedia/en/thumb/f/fc/Royal_Moroccan_Football_Federation_logo.svg/120px-Royal_Moroccan_Football_Federation_logo.svg.png",
    "Japan": "https://upload.wikimedia.org/wikipedia/en/thumb/8/89/Japan_Football_Association_crest.svg/120px-Japan_Football_Association_crest.svg.png",
}

# Simple team-colour map used for the initials-badge fallback (hex).
TEAM_COLORS = {
    "Argentina": "#6CACE4", "Brazil": "#FEDF00", "France": "#001489",
    "England": "#CE1124", "Spain": "#AA151B", "Germany": "#000000",
    "Portugal": "#006600", "Netherlands": "#F36C21", "Belgium": "#E30613",
    "Croatia": "#C8102E", "United States": "#0A3161", "Canada": "#D80621",
    "Mexico": "#006847", "Uruguay": "#5CBFEB", "Morocco": "#C1272D",
    "Japan": "#0033A0", "Norway": "#BA0C2F", "Switzerland": "#D52B1E",
    "Sweden": "#FECC02", "Austria": "#ED2939",
}
DEFAULT_TEAM_COLOR = "#334155"

# --------------------------------------------------------------------------- #
# Team -> Wikipedia national-team article. Most follow the default pattern;
# a few need explicit overrides. Used for the all-time head-to-head table.
# --------------------------------------------------------------------------- #
TEAM_WIKI_OVERRIDES = {
    "United States": "United States men's national soccer team",
    "South Korea": "South Korea national football team",
    "Ivory Coast": "Ivory Coast national football team",
    "DR Congo": "DR Congo national football team",
    "Cape Verde": "Cape Verde national football team",
}


def wiki_team_url(team):
    """Return the Wikipedia article URL for a national team."""
    title = TEAM_WIKI_OVERRIDES.get(team, f"{team} national football team")
    return f"{WIKI_BASE}/wiki/{title.replace(' ', '_')}"


# --------------------------------------------------------------------------- #
# Team -> ISO 3166-1 alpha-2 code, for real flag images via flagcdn.com.
# Home nations use flagcdn's gb-* subdivision codes.
# --------------------------------------------------------------------------- #
FLAG_BASE = "https://flagcdn.com/w80"

TEAM_ISO = {
    "Argentina": "ar", "Australia": "au", "Austria": "at", "Algeria": "dz",
    "Belgium": "be", "Bosnia and Herzegovina": "ba", "Brazil": "br",
    "Canada": "ca", "Cape Verde": "cv", "Colombia": "co", "Croatia": "hr",
    "Curaçao": "cw", "Czech Republic": "cz", "Denmark": "dk", "DR Congo": "cd",
    "Ecuador": "ec", "Egypt": "eg", "England": "gb-eng", "France": "fr",
    "Germany": "de", "Ghana": "gh", "Haiti": "ht", "Iran": "ir", "Iraq": "iq",
    "Italy": "it", "Ivory Coast": "ci", "Japan": "jp", "Jordan": "jo",
    "Mexico": "mx", "Morocco": "ma", "Netherlands": "nl", "New Zealand": "nz",
    "Nigeria": "ng", "Norway": "no", "Panama": "pa", "Paraguay": "py",
    "Poland": "pl", "Portugal": "pt", "Qatar": "qa", "Saudi Arabia": "sa",
    "Scotland": "gb-sct", "Senegal": "sn", "South Africa": "za",
    "South Korea": "kr", "Spain": "es", "Sweden": "se", "Switzerland": "ch",
    "Tunisia": "tn", "Turkey": "tr", "United States": "us", "Uruguay": "uy",
    "Uzbekistan": "uz", "Wales": "gb-wls",
}


def flag_url(team):
    """Return a flag image URL for a team, or None if unmapped."""
    code = TEAM_ISO.get(team)
    return f"{FLAG_BASE}/{code}.png" if code else None


def all_flags():
    """team -> flag URL, for every mapped team (injected into the dashboard)."""
    return {team: f"{FLAG_BASE}/{code}.png" for team, code in TEAM_ISO.items()}

