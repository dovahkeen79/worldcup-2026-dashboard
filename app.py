"""
Flask web app — the interactive World Cup 2026 dashboard.

Routes
  GET  /                 the dashboard page
  GET  /api/tournament   the full tournament JSON (builds it once if missing)
  POST /api/refresh      re-scrapes everything and rewrites tournament.json

Run:  python app.py     then open http://127.0.0.1:5000
(or just double-click WorldCup.bat)
"""

from flask import Flask, jsonify, render_template

from build_data import TOURNAMENT_JSON, build_and_save
from config import DEFAULT_TEAM_COLOR, TEAM_COLORS, all_flags
from core.logger import get_logger
from core.storage import load_json

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.jinja_env.auto_reload = True
log = get_logger("app")


@app.route("/")
def index():
    return render_template(
        "dashboard.html",
        flags=all_flags(),
        colors=TEAM_COLORS,
        default_color=DEFAULT_TEAM_COLOR,
        is_static=False,
        data_url="/api/tournament",
        embedded=None,
    )


@app.route("/api/tournament")
def api_tournament():
    data = load_json(TOURNAMENT_JSON)
    if not data:
        log.info("No cached tournament data — building on first request")
        data = build_and_save()
    return jsonify(data)


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    log.info("Manual refresh requested")
    try:
        data = build_and_save()
        return jsonify({"ok": True, "counts": data.get("counts", {}),
                        "generated_label": data.get("generated_label")})
    except Exception as exc:  # noqa: BLE001
        log.exception("Refresh failed")
        return jsonify({"ok": False, "error": str(exc)}), 500


if __name__ == "__main__":
    # threaded=True so the long refresh doesn't block serving static assets.
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
