"""
One-off API-Football coverage test (runs inside GitHub Actions).

Confirms, WITHOUT exposing the key, whether the free plan actually returns
2026 World Cup lineups + formations. It prints a short report and never logs
the key itself.

Assumes the direct api-sports.io access (free account at dashboard.api-football.com),
which uses the `x-apisports-key` header.
"""

import json
import os
import urllib.parse
import urllib.request

KEY = os.environ.get("API_FOOTBALL_KEY", "").strip()
BASE = "https://v3.football.api-sports.io"


def call(path):
    # Encode spaces / special chars in the query string.
    if "?" in path:
        base, qs = path.split("?", 1)
        path = base + "?" + urllib.parse.quote(qs, safe="=&")
    req = urllib.request.Request(BASE + path, headers={"x-apisports-key": KEY})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main():
    if not KEY:
        print("❌ NO KEY: the API_FOOTBALL_KEY secret is empty / not set.")
        raise SystemExit(1)
    print("Key detected (length %d) — not printing it.\n" % len(KEY))

    # 1) account status + remaining requests
    try:
        st = call("/status").get("response", {}) or {}
    except Exception as exc:  # noqa: BLE001
        print("❌ /status failed:", exc, "\n   (If this is a 401/403, the key or "
              "access method is wrong — this script assumes api-sports.io direct.)")
        raise SystemExit(1)
    sub = st.get("subscription", {})
    reqs = st.get("requests", {})
    print("PLAN:", sub.get("plan"), "| active:", sub.get("active"),
          "| requests today:", reqs.get("current"), "/", reqs.get("limit_day"))

    # 2) World Cup league + whether the 2026 season has LINEUP coverage on this plan
    lg = call("/leagues?search=World Cup")
    wc = next((L for L in lg.get("response", [])
               if L["league"]["name"] == "World Cup" and L["league"]["type"] == "Cup"), None)
    if not wc:
        print("❌ Could not find a 'World Cup' league for this key/plan.")
        raise SystemExit(0)
    lid = wc["league"]["id"]
    years = sorted(s["year"] for s in wc["seasons"])
    print("\nWorld Cup league id:", lid, "| seasons on this plan:", years)
    s2026 = next((s for s in wc["seasons"] if s["year"] == 2026), None)
    print("2026 season present on plan:", bool(s2026))
    if s2026:
        cov = (s2026.get("coverage") or {}).get("fixtures", {})
        print("2026 coverage -> lineups:", cov.get("lineups"),
              "| events:", cov.get("events"), "| statistics:", cov.get("statistics_fixtures"))

    # 3) do 2026 fixtures come back, and can we get a real lineup?
    fx = call(f"/fixtures?league={lid}&season=2026")
    fixtures = fx.get("response", [])
    print("\n2026 fixtures returned:", len(fixtures), "| api errors:", fx.get("errors"))
    finished = [f for f in fixtures
                if f["fixture"]["status"]["short"] in ("FT", "AET", "PEN")]
    if not finished:
        print("No finished 2026 fixtures to test a lineup on.")
        raise SystemExit(0)

    f0 = finished[0]
    fid = f0["fixture"]["id"]
    home = f0["teams"]["home"]["name"]
    away = f0["teams"]["away"]["name"]
    ln = call(f"/fixtures/lineups?fixture={fid}")
    resp = ln.get("response", [])
    print(f"\nLINEUP test — {home} vs {away} (fixture {fid}):"
          f" teams_with_lineup={len(resp)} | api errors: {ln.get('errors')}")
    for t in resp:
        print("  •", t["team"]["name"],
              "| formation:", t.get("formation"),
              "| startXI:", len(t.get("startXI") or []),
              "| subs:", len(t.get("substitutes") or []),
              "| coach:", (t.get("coach") or {}).get("name"))

    ok = bool(resp) and any(t.get("formation") and t.get("startXI") for t in resp)
    print("\n=== VERDICT:", "✅ 2026 lineups + formations ARE available on the free plan."
          if ok else "❌ No usable 2026 lineup/formation data on the free plan.")


if __name__ == "__main__":
    main()
