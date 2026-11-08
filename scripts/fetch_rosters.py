#!/usr/bin/env python3
"""Exact weekly rosters for backtesting waiver advice: bt/rosters.json.gz.
Walks public leagues from the seed user through leaguemates (and theirs...) and keeps completed seasons of any league type
(redraft, keeper, dynasty; best ball skipped). Per league it saves numbers only: settings incl. FAAB budget and waiver type,
every week's full rosters and starters, every transaction (with FAAB bids) and the draft. League ids are hashed;
no usernames, team names or league names are stored."""
import gzip, json, os, time
from collections import deque
import fetch_keepers as fk

MAX_LEAGUES = int(os.environ.get("MAX_LEAGUES", "900"))
TIME_LIMIT = float(os.environ.get("TIME_LIMIT_MIN", "300")) * 60
SEASONS = [2022, 2023, 2024, 2025]
OUT = "bt/rosters.json.gz"
T0 = time.time()


def main():
    old = json.load(gzip.open(OUT, "rt")) if os.path.exists(OUT) else {"leagues": {}}
    lgs = old["leagues"]; done = set(old.get("seen", []))
    u = fk.get(f"/user/{fk.SEED}")
    if not u: print("seed user not found"); return
    q, seen_users, walked, added = deque([u["user_id"]]), {u["user_id"]}, set(), 0
    while q and len(lgs) < MAX_LEAGUES and time.time() - T0 < TIME_LIMIT:
        uid = q.popleft()
        for s in SEASONS:
            for lg in fk.get(f"/user/{uid}/leagues/nfl/{s}") or []:
                lid = lg.get("league_id")
                if not lid: continue
                h = fk.hid(lid)
                if h not in walked and len(seen_users) < 60000:
                    walked.add(h)
                    for m in fk.get(f"/league/{lid}/users") or []:
                        if m.get("user_id") and m["user_id"] not in seen_users: seen_users.add(m["user_id"]); q.append(m["user_id"])
                st = lg.get("settings") or {}
                if h in done or lg.get("status") != "complete" or st.get("best_ball"): continue
                done.add(h)
                pack = fk.season_pack(lg)
                if not pack["weeks"]: continue
                pack.update({"waiver_budget": st.get("waiver_budget"), "waiver_type": st.get("waiver_type")})
                lgs[h] = pack; added += 1
                if added % 25 == 0: print(f"{len(lgs)} leagues, {fk.CALLS[0]} calls, {int((time.time()-T0)/60)} min", flush=True)
                if len(lgs) >= MAX_LEAGUES or time.time() - T0 >= TIME_LIMIT: break
            if len(lgs) >= MAX_LEAGUES or time.time() - T0 >= TIME_LIMIT: break
    old["seen"] = sorted(done); old["built"] = time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime())
    with gzip.open(OUT, "wt") as f: json.dump(old, f, separators=(",", ":"))
    print(f"saved {len(lgs)} leagues ({added} new), {fk.CALLS[0]} API calls, {int((time.time()-T0)/60)} min")


if __name__ == "__main__":
    main()
