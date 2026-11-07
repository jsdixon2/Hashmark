#!/usr/bin/env python3
"""Archive Sleeper's weekly projections for model backtests (bt/sleeper_proj.json.gz).
Runs in GitHub Actions because Sleeper is reachable there. Keeps QB/RB/WR/TE with a projection,
and only the stats needed to rescore any league: pts_ppr/half/std plus the main counting stats."""
import gzip, json, os, time, urllib.request
from datetime import datetime, timezone

API = "https://api.sleeper.app/v1"
KEEP = ["pts_ppr", "pts_half_ppr", "pts_std", "rec", "rec_yd", "rec_td", "rush_yd", "rush_td", "pass_yd", "pass_td", "pass_int", "fum_lost", "rec_tgt", "rush_att", "pass_att", "gp"]
OUT = "bt/sleeper_proj.json.gz"


def get(u):
    for k in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "hashmark-backtest"}), timeout=60) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            print("  retry", u, e); time.sleep(2 + 3 * k)
    return None


def main():
    state = get(f"{API}/state/nfl") or {}
    cur_season, cur_week = int(state.get("season") or datetime.now(timezone.utc).year), int(state.get("week") or 1)
    old = {}
    if os.path.exists(OUT):
        old = json.load(gzip.open(OUT, "rt"))
    out = {"built": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "w": old.get("w", {})}
    for season in range(2021, cur_season + 1):
        last = 18 if season < cur_season else max(1, cur_week)
        for wk in range(1, last + 1):
            key = f"{season}-{wk}"
            if key in out["w"] and season < cur_season:
                continue
            j = get(f"{API}/projections/nfl/regular/{season}/{wk}")
            if j is None:
                continue
            rows = j if isinstance(j, list) else [dict(player_id=k, stats=v) for k, v in j.items()]
            keep = {}
            for r in rows:
                st = r.get("stats") or r
                pos = (r.get("player") or {}).get("position") or r.get("position")
                pid = str(r.get("player_id") or "")
                if not pid or (pos and pos not in ("QB", "RB", "WR", "TE")):
                    continue
                if (st.get("pts_ppr") or 0) < 0.5:
                    continue
                keep[pid] = {k: round(st[k], 2) for k in KEEP if isinstance(st.get(k), (int, float))}
                if pos: keep[pid]["pos"] = pos
            out["w"][key] = keep
            print(key, len(keep))
            time.sleep(0.4)
    os.makedirs("bt", exist_ok=True)
    with gzip.open(OUT, "wt") as f:
        json.dump(out, f, separators=(",", ":"))


if __name__ == "__main__":
    main()
