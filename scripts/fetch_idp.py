#!/usr/bin/env python3
"""IDP data for testing Hashmark's IDP values and taxi/IR rules (runs in GitHub Actions; Sleeper is reachable there).
bt/idp/players.json.gz  sleeper id -> [fantasy pos, birth date, years_exp] for DL/LB/DB
bt/idp/season.json.gz   season totals 2014+ (IDP stats only, IDP players only)
bt/idp/weekly.json.gz   weekly IDP stats 2021+
bt/idp/rules.json       anonymous counts of taxi / IR settings across public dynasty leagues"""
import gzip, json, os, time, urllib.request, collections
API = "https://api.sleeper.app/v1"; OUT = "bt/idp"
MAP = {"DE": "DL", "DT": "DL", "NT": "DL", "DL": "DL", "LB": "LB", "ILB": "LB", "OLB": "LB", "MLB": "LB", "CB": "DB", "S": "DB", "SS": "DB", "FS": "DB", "DB": "DB"}
def get(p):
    for k in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(API + p, headers={"User-Agent": "hashmark-backtest"}), timeout=90) as r: return json.loads(r.read().decode())
        except Exception as e: print("retry", p, e); time.sleep(2 + 3 * k)
    return None
def rows(j): return j if isinstance(j, list) else [dict(player_id=k, stats=v) for k, v in (j or {}).items()]
def main():
    os.makedirs(OUT, exist_ok=True)
    P = get("/players/nfl") or {}; ids = {}
    for pid, m in P.items():
        fp = next((x for x in (m.get("fantasy_positions") or []) if x in ("DL", "LB", "DB")), None) or MAP.get(m.get("position"))
        if fp and m.get("position") not in ("QB", "RB", "WR", "TE"): ids[pid] = [fp, m.get("birth_date"), m.get("years_exp")]
    json.dump(ids, gzip.open(f"{OUT}/players.json.gz", "wt")); print(len(ids), "IDP players")
    keepk = lambda s: {k: round(v, 2) for k, v in s.items() if isinstance(v, (int, float)) and (k.startswith("idp_") or k in ("gp", "def_snp", "tm_def_snp", "gs"))}
    st = get("/state/nfl") or {}; cur = int(st.get("season") or 2026); wk = int(st.get("week") or 1)
    season = {}
    for y in range(2014, cur + 1):
        j = get(f"/stats/nfl/regular/{y}"); season[str(y)] = {r["player_id"]: keepk(r.get("stats") or r) for r in rows(j) if str(r.get("player_id")) in ids}; time.sleep(.3)
        print(y, len(season[str(y)]))
    json.dump(season, gzip.open(f"{OUT}/season.json.gz", "wt"))
    weekly = {}
    for y in range(2021, cur + 1):
        for w in range(1, (18 if y < cur else wk) + 1):
            j = get(f"/stats/nfl/regular/{y}/{w}"); weekly[f"{y}-{w}"] = {str(r["player_id"]): keepk(r.get("stats") or r) for r in rows(j) if str(r.get("player_id")) in ids and (r.get("stats") or r).get("gp")}; time.sleep(.3)
    json.dump(weekly, gzip.open(f"{OUT}/weekly.json.gz", "wt"))
    # anonymous taxi / IR rule counts from public 2026 dynasty leagues reached from the seed user
    from collections import deque
    u = get("/user/jackdixon"); q = deque([u["user_id"]]) if u else deque(); seen = set(q); C = collections.Counter(); n = 0; done = set()
    while q and n < 400:
        for lg in get(f"/user/{q.popleft()}/leagues/nfl/{cur}") or []:
            if lg["league_id"] in done: continue
            done.add(lg["league_id"]); s = lg.get("settings") or {}
            if s.get("type") == 2:
                n += 1
                for k in ("taxi_slots", "taxi_years", "taxi_allow_vets", "taxi_deadline", "reserve_slots", "reserve_allow_out", "reserve_allow_doubtful", "reserve_allow_sus", "reserve_allow_na", "reserve_allow_dnr", "reserve_allow_cov"): C[f"{k}={s.get(k)}"] += 1
            if len(seen) < 3000:
                for m in get(f"/league/{lg['league_id']}/users") or []:
                    if m["user_id"] not in seen: seen.add(m["user_id"]); q.append(m["user_id"])
    json.dump({"leagues": n, "counts": dict(sorted(C.items()))}, open(f"{OUT}/rules.json", "w"), indent=1)
if __name__ == "__main__": main()
