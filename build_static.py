"""
Build a fully static version of the dashboard for GitHub Pages.

Renders the same dashboard template with the tournament data **baked in**, so
the result is a single self-contained `docs/index.html` that needs no Python
server — anyone can open it via a GitHub Pages link (or by double-clicking).

Usage:
    python build_static.py            # re-scrape fresh data, then build
    python build_static.py --no-fetch # reuse the existing data snapshot
"""

import sys

from jinja2 import Environment, FileSystemLoader, select_autoescape

from build_data import TOURNAMENT_JSON, build_and_save
from config import DEFAULT_TEAM_COLOR, ROOT, TEAM_COLORS, TEMPLATES_DIR, all_flags
from core.logger import get_logger, setup_logging
from core.storage import load_json

log = get_logger("build_static")
DOCS_DIR = ROOT / "docs"


def build_static(refresh=True):
    setup_logging()
    data = build_and_save() if refresh else (load_json(TOURNAMENT_JSON) or build_and_save())

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    html = env.get_template("dashboard.html").render(
        flags=all_flags(),
        colors=TEAM_COLORS,
        default_color=DEFAULT_TEAM_COLOR,
        is_static=True,
        data_url="",
        embedded=data,
    )

    DOCS_DIR.mkdir(exist_ok=True)
    (DOCS_DIR / "index.html").write_text(html, encoding="utf-8")
    # Tell GitHub Pages not to run Jekyll (it would ignore some files).
    (DOCS_DIR / ".nojekyll").write_text("", encoding="utf-8")

    out = DOCS_DIR / "index.html"
    log.info("Static site written -> %s (%d KB)", out, out.stat().st_size // 1024)
    return out


if __name__ == "__main__":
    build_static(refresh="--no-fetch" not in sys.argv)
