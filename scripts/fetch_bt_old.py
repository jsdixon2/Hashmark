#!/usr/bin/env python3
"""One-off backfill (owner 2026-11-16): Sleeper's weekly projections and final stat lines for older seasons
(default 2018-2020), so projection tests can fit on more than 2021-24. Same fields as scripts/fetch_bt.py, but written
to SEPARATE files (bt/sleeper_proj_old.json.gz, bt/sleeper_stats_old.json.gz) so the report and existing backtests,
which read bt/sleeper_proj.json.gz, are unchanged. Prints a per-week coverage summary (players with a projection,
how many also have a stat line) so we can judge whether Sleeper's old projections are usable.
Run: python3 scripts/fetch_bt_old.py [first] [last]   (Actions only: Sleeper is not reachable from the cloud sessions)"""
import gzip, json, os, sys, time, urllib.request
from datetime import datetime, timezone

API = "https://api.sleeper.app/v1"
KEEP = ["pts_ppr", "pts_half_ppr", "pts_std", "rec", "rec_yd", "rec_td", "rush_yd", "rush_td", "pass_yd", "pass_td",
        "pass_int", "fum_lost", "rec_tgt", "rush_att", "pass_att", "gp"]
first = int(sys.argv[1]) if len(sys.argv) > 1 else 2018
last = int(sys.argv[2]) if len(sys.argv) > 2 else 2020
OP, OS = "bt/sleeper_proj_old.json.gz", "bt/sleeper_stats_old.json.gz"


def get(u):
    for k in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "hashmark-backtest"}), timeout=60) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            print("  retry", u, e); time.sleep(2 + 3 * k)
    return None


def rows_of(j):
    return j if isinstance(j, list) else [dict(player_id=k, stats=v) for k, v in (j or {}).items()]


def main():
    P = json.load(gzip.open(OP, "rt")) if os.path.exists(OP) else {"w": {}}
    S = json.load(gzip.open(OS, "rt")) if os.path.exists(OS) else {"w": {}}
    summ = []
    for season in range(first, last + 1):
        for wk in range(1, 19):
            key = f"{season}-{wk}"
            pj = get(f"{API}/projections/nfl/regular/{season}/{wk}")
            keep = {}
            for r in rows_of(pj):
                st = r.get("stats") or r
                pos = (r.get("player") or {}).get("position") or r.get("position")
                pid = str(r.get("player_id") or "")
                if not pid or (pos and pos not in ("QB", "RB", "WR", "TE")) or (st.get("pts_ppr") or 0) < 0.5:
                    continue
                keep[pid] = {k: round(st[k], 2) for k in KEEP if isinstance(st.get(k), (int, float))}
                if pos: keep[pid]["pos"] = pos
            sj = get(f"{API}/stats/nfl/regular/{season}/{wk}")
            sk = {}
            for r in rows_of(sj):
                s_ = r.get("stats") or r; pid = str(r.get("player_id") or "")
                if pid and (s_.get("gp") or 0) > 0:
                    sk[pid] = {k: round(s_[k], 2) for k in KEEP if isinstance(s_.get(k), (int, float))}
            if keep: P["w"][key] = keep
            if sk: S["w"][key] = sk
            both = sum(1 for p in keep if p in sk)
            summ.append((key, len(keep), len(sk), both))
            print(f"{key}: projections {len(keep)}, stat lines {len(sk)}, both {both}", flush=True)
            time.sleep(0.4)
    P["built"] = S["built"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    os.makedirs("bt", exist_ok=True)
    with gzip.open(OP, "wt") as f: json.dump(P, f, separators=(",", ":"))
    with gzip.open(OS, "wt") as f: json.dump(S, f, separators=(",", ":"))
    print("\nseason  weeks-with-projections  avg-projected  avg-matched")
    for y in range(first, last + 1):
        rr = [x for x in summ if x[0].startswith(f"{y}-") and x[1]]
        print(y, len(rr), round(sum(x[1] for x in rr) / max(1, len(rr))), round(sum(x[3] for x in rr) / max(1, len(rr))))


if __name__ == "__main__":
    main()
