#!/usr/bin/env python3
"""Anonymous fantasy-matchup archive for model backtests: bt/leagues.json.gz.
Starts from one Sleeper user's leagues and follows leaguemates to their other public leagues (seasons 2021+),
up to MAX_LEAGUES league-seasons. Saves only numbers: league settings, weekly scores, starters (NFL player ids),
standings and playoff results. League ids are hashed; no usernames, team names or league names are stored."""
import gzip, hashlib, json, os, time, urllib.request
from collections import deque

API = "https://api.sleeper.app/v1"
SEED = os.environ.get("SEED_USER", "jackdixon")
MAX_LEAGUES = int(os.environ.get("MAX_LEAGUES", "700"))
SEASONS = [2021, 2022, 2023, 2024, 2025, 2026]
OUT = "bt/leagues.json.gz"
CALLS = [0]


def get(path):
    for k in range(4):
        try:
            CALLS[0] += 1
            with urllib.request.urlopen(urllib.request.Request(API + path, headers={"User-Agent": "hashmark-backtest"}), timeout=40) as r:
                time.sleep(0.07)
                return json.loads(r.read().decode() or "null")
        except urllib.error.HTTPError as e:
            if e.code == 429: time.sleep(10); continue
            if e.code == 404: return None
            time.sleep(2)
        except Exception:
            time.sleep(2 + 2 * k)
    return None


def hid(x):
    return hashlib.sha1(("hm:" + str(x)).encode()).hexdigest()[:12]


def league_pack(lg):
    lid = lg["league_id"]; st = lg.get("settings") or {}
    if st.get("best_ball") or (lg.get("status") not in ("complete", "in_season")): return None
    rosters = get(f"/league/{lid}/rosters") or []
    if len(rosters) < 4: return None
    pws = int(st.get("playoff_week_start") or 15) or 15
    last = 17 if int(lg.get("season")) <= 2020 else 18
    weeks = {}
    for w in range(1, last + 1):
        m = get(f"/league/{lid}/matchups/{w}")
        if not m: continue
        rows = []
        for t in m:
            if t.get("points") is None: continue
            rows.append([t.get("roster_id"), t.get("matchup_id"), round(float(t.get("points") or 0), 2), [s for s in (t.get("starters") or []) if s and s != "0"]])
        if rows and any(r[2] for r in rows): weeks[w] = rows
    br = get(f"/league/{lid}/winners_bracket") or []
    sc = lg.get("scoring_settings") or {}
    keep_sc = {k: sc[k] for k in ("rec", "bonus_rec_te", "pass_td", "pass_int", "pass_yd", "rush_yd", "rec_yd", "rush_td", "rec_td", "fum_lost") if k in sc}
    return {"id": hid(lid), "season": int(lg.get("season")), "status": lg.get("status"), "type": st.get("type"), "n": st.get("num_teams") or len(rosters),
            "pws": pws, "pteams": st.get("playoff_teams"), "lws": st.get("last_scored_leg") or st.get("leg"), "pos": lg.get("roster_positions"),
            "sc": keep_sc, "guillotine": 1 if (st.get("type") == 3 or "guillotine" in (lg.get("name") or "").lower() or "chopped" in (lg.get("name") or "").lower()) else 0,
            "rost": [[r.get("roster_id"), (r.get("settings") or {}).get("wins"), (r.get("settings") or {}).get("losses"), (r.get("settings") or {}).get("ties"),
                      (r.get("settings") or {}).get("fpts")] for r in rosters],
            "weeks": weeks, "bracket": [[b.get("r"), b.get("m"), b.get("t1"), b.get("t2"), b.get("w"), b.get("l"), b.get("p")] for b in br]}


def main():
    old = json.load(gzip.open(OUT, "rt")) if os.path.exists(OUT) else {"leagues": {}}
    done = set(old.get("seen", []))
    u = get(f"/user/{SEED}")
    if not u: print("seed user not found"); return
    q, seen_users = deque([u["user_id"]]), {u["user_id"]}
    added = 0
    while q and len(old["leagues"]) < MAX_LEAGUES:
        uid = q.popleft()
        for s in SEASONS:
            for lg in get(f"/user/{uid}/leagues/nfl/{s}") or []:
                lid = lg.get("league_id")
                if not lid or hid(lid) in done: continue
                done.add(hid(lid))
                # leaguemates feed the crawl
                for m in get(f"/league/{lid}/users") or []:
                    if m.get("user_id") and m["user_id"] not in seen_users and len(seen_users) < 20000:
                        seen_users.add(m["user_id"]); q.append(m["user_id"])
                pk = league_pack(lg)
                if pk and pk["weeks"]:
                    old["leagues"][pk["id"]] = pk; added += 1
                    if added % 25 == 0: print(f"{len(old['leagues'])} leagues, {CALLS[0]} calls")
                if len(old["leagues"]) >= MAX_LEAGUES: break
            if len(old["leagues"]) >= MAX_LEAGUES: break
    old["seen"] = sorted(done)
    old["built"] = time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime())
    os.makedirs("bt", exist_ok=True)
    with gzip.open(OUT, "wt") as f: json.dump(old, f, separators=(",", ":"))
    print(f"saved {len(old['leagues'])} league-seasons ({added} new), {CALLS[0]} API calls")


if __name__ == "__main__":
    main()
