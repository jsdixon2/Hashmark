#!/usr/bin/env python3
"""Keeper-league archive for testing Hashmark's keeper trade logic against what actually happened: bt/keepers.json.gz.
Walks public leagues from the seed user through leaguemates (and their leaguemates...) and keeps every keeper league
(Sleeper league type 1) that has a following season. For each pair it saves numbers only:
  season s : settings (slots, scoring, keeper count, roster/IR/taxi sizes), the draft (with keeper picks and slots),
             every week's full rosters and starters, and every transaction
  season s+1: the draft (who each team kept and in which round = the keeper's cost), keeper count
League ids are hashed; no usernames, team names or league names are stored."""
import gzip, hashlib, json, os, time, urllib.request
from collections import deque

API = "https://api.sleeper.app/v1"
SEED = os.environ.get("SEED_USER", "jackdixon")
MAX_PAIRS = int(os.environ.get("MAX_PAIRS", "450"))
TIME_LIMIT = float(os.environ.get("TIME_LIMIT_MIN", "290")) * 60
SEASONS = [2022, 2023, 2024, 2025, 2026]
OUT = "bt/keepers.json.gz"
T0 = time.time(); CALLS = [0]


def get(path):
    for k in range(4):
        try:
            CALLS[0] += 1
            with urllib.request.urlopen(urllib.request.Request(API + path, headers={"User-Agent": "hashmark-backtest"}), timeout=40) as r:
                time.sleep(0.06); return json.loads(r.read().decode() or "null")
        except urllib.error.HTTPError as e:
            if e.code == 429: time.sleep(10); continue
            if e.code == 404: return None
            time.sleep(2)
        except Exception:
            time.sleep(2 + 2 * k)
    return None


def hid(x): return hashlib.sha1(("hm:" + str(x)).encode()).hexdigest()[:12]
KEEP_SC = ("rec", "bonus_rec_te", "bonus_rec_rb", "bonus_rec_wr", "pass_td", "pass_int", "pass_yd", "rush_yd", "rec_yd", "rush_td", "rec_td", "fum_lost", "rush_att", "pass_att", "pass_2pt", "rush_2pt", "rec_2pt")


def draft_pack(draft_id):
    if not draft_id: return None
    d = get(f"/draft/{draft_id}") or {}; picks = get(f"/draft/{draft_id}/picks") or []
    return {"type": d.get("type"), "season": d.get("season"), "rounds": (d.get("settings") or {}).get("rounds"), "status": d.get("status"),
            "s2r": d.get("slot_to_roster_id") or {}, "start": d.get("start_time"),
            "picks": [[p.get("round"), p.get("pick_no"), p.get("player_id"), p.get("roster_id"), 1 if p.get("is_keeper") else 0, p.get("draft_slot"),
                       int(((p.get("metadata") or {}).get("amount") or 0) or 0)] for p in picks]}


def season_pack(lg):
    lid = lg["league_id"]; st = lg.get("settings") or {}; sc = lg.get("scoring_settings") or {}
    weeks = {}
    for w in range(1, 19):
        m = get(f"/league/{lid}/matchups/{w}")
        if not m: continue
        rows = [[t.get("roster_id"), t.get("matchup_id"), round(float(t.get("points") or 0), 2), [s for s in (t.get("starters") or []) if s and s != "0"], t.get("players") or []] for t in m if t.get("points") is not None]
        if rows and any(r[2] for r in rows): weeks[w] = rows
    tx = []
    for w in range(1, 19):
        for t in get(f"/league/{lid}/transactions/{w}") or []:
            if t.get("status") != "complete": continue
            tx.append([t.get("type"), w, t.get("roster_ids") or [], t.get("adds") or {}, t.get("drops") or {},
                       [[p.get("season"), p.get("round"), p.get("roster_id"), p.get("previous_owner_id"), p.get("owner_id")] for p in (t.get("draft_picks") or [])],
                       [[b.get("sender"), b.get("receiver"), b.get("amount")] for b in (t.get("waiver_budget") or [])],
                       (t.get("settings") or {}).get("waiver_bid"), t.get("status_updated") or t.get("created")])
    return {"id": hid(lid), "season": int(lg.get("season")), "type": st.get("type"), "n": st.get("num_teams"), "pos": lg.get("roster_positions"),
            "sc": {k: sc[k] for k in sc if k in KEEP_SC}, "pws": st.get("playoff_week_start"), "max_keepers": st.get("max_keepers"),
            "reserve": st.get("reserve_slots"), "taxi": st.get("taxi_slots"), "draft_rounds": st.get("draft_rounds"),
            "weeks": weeks, "tx": tx, "draft": draft_pack(lg.get("draft_id"))}


def main():
    old = json.load(gzip.open(OUT, "rt")) if os.path.exists(OUT) else {"pairs": {}}
    pairs = old["pairs"]; done = set(old.get("seen", []))
    u = get(f"/user/{SEED}")
    if not u: print("seed user not found"); return
    q, seen_users, walked, added = deque([u["user_id"]]), {u["user_id"]}, set(), 0
    while q and len(pairs) < MAX_PAIRS and time.time() - T0 < TIME_LIMIT:
        uid = q.popleft()
        for s in SEASONS:
            for lg in get(f"/user/{uid}/leagues/nfl/{s}") or []:
                lid = lg.get("league_id")
                if not lid: continue
                h = hid(lid)
                if h not in walked and len(seen_users) < 60000:
                    walked.add(h)
                    for m in get(f"/league/{lid}/users") or []:
                        if m.get("user_id") and m["user_id"] not in seen_users: seen_users.add(m["user_id"]); q.append(m["user_id"])
                st = lg.get("settings") or {}
                if st.get("type") != 1 or not lg.get("previous_league_id") or h in done or st.get("best_ball"): continue
                done.add(h)
                prev = get(f"/league/{lg['previous_league_id']}")
                if not prev or (prev.get("settings") or {}).get("type") != 1 or prev.get("status") != "complete": continue
                nxt = {"id": h, "season": int(lg.get("season")), "max_keepers": st.get("max_keepers"), "draft": draft_pack(lg.get("draft_id")), "status": lg.get("status")}
                if not nxt["draft"] or not any(p[4] for p in nxt["draft"]["picks"]): continue  # keepers must be visible in the next draft
                cur = season_pack(prev)
                if not cur["weeks"] or not cur["draft"]: continue
                pairs[cur["id"]] = {"s": cur, "next": nxt}; added += 1
                if added % 20 == 0: print(f"{len(pairs)} keeper pairs, {CALLS[0]} calls, {int((time.time()-T0)/60)} min")
                if len(pairs) >= MAX_PAIRS or time.time() - T0 >= TIME_LIMIT: break
            if len(pairs) >= MAX_PAIRS or time.time() - T0 >= TIME_LIMIT: break
    old["seen"] = sorted(done); old["built"] = time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime())
    os.makedirs("bt", exist_ok=True)
    with gzip.open(OUT, "wt") as f: json.dump(old, f, separators=(",", ":"))
    print(f"saved {len(pairs)} keeper league pairs ({added} new), {CALLS[0]} API calls, {int((time.time()-T0)/60)} min")


if __name__ == "__main__":
    main()
