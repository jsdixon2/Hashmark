"""Edge test 3: does the crowd overreact? Crowd = real managers in bt/rosters.json.gz (900 leagues 2022-25).
Drop rate of a player in week w = leagues that dropped him in week w / leagues rostering him in week w-1 (20+ leagues).
Usage stable = last game's offensive snap share >= 90% of his previous-3-game average and that average >= 50%.
Outcome: next 3 weeks (w..w+2) real PPR points minus Sleeper's projection, per game played. Same for add rate (crowd
piling onto a player). Benchmark: all other rostered players with the same projection band."""
import gzip, json, csv, collections, statistics as st
R = json.load(gzip.open("bt/rosters.json.gz", "rt"))["leagues"]
SP = json.load(gzip.open("bt/sleeper_proj.json.gz", "rt"))["w"]; ST = json.load(gzip.open("bt/sleeper_stats.json.gz", "rt"))["w"]
p2s = {}; pos = {}
for r in csv.DictReader(open("backtest/dl/ids.csv", encoding="utf-8")):
    s = str(r.get("sleeper_id") or "").split(".")[0]
    if s in ("", "NA"): continue
    pos[s] = r.get("position")
    if r.get("pfr_id") not in ("", "NA", None): p2s[r["pfr_id"]] = s
SN = {}
for y in range(2022, 2026):
    for r in csv.DictReader(open(f"backtest/dl/snap_{y}.csv", encoding="utf-8")):
        s = p2s.get(r["pfr_player_id"])
        if s and r["game_type"] == "REG": SN[(y, int(r["week"]), s)] = float(r["offense_pct"] or 0)
ros = collections.Counter(); drops = collections.Counter(); adds = collections.Counter()
for l in R.values():
    y = l["season"]
    for wk, ms in l["weeks"].items():
        for t in ms:
            for pid in set(t[4]): ros[(y, int(wk), pid)] += 1
    for t in l["tx"]:
        if t[0] in ("waiver", "free_agent"):
            for pid in t[4]: drops[(y, t[1], pid)] += 1
            for pid in t[3]: adds[(y, t[1], pid)] += 1
def snaps(y, w, pid):
    last = SN.get((y, w - 1, pid)); prev = [SN.get((y, w - k, pid)) for k in (2, 3, 4)]; prev = [x for x in prev if x is not None]
    if last is None or len(prev) < 2: return None
    m = st.mean(prev); return "stable" if m >= .5 and last >= .9 * m else "down" if last < .8 * m else "other"
def fut(y, w, pid):
    a = p = 0; g = 0
    for k in range(w, w + 3):
        s = ST.get(f"{y}-{k}", {}).get(pid); pr = SP.get(f"{y}-{k}", {}).get(pid)
        if s and s.get("gp") and pr: a += s.get("pts_ppr") or 0; p += pr.get("pts_ppr") or 0; g += 1
    return (a - p) / g if g else None, (a / g if g else None), (p / g if g else None)
G = collections.defaultdict(list)
for (y, w, pid), n in ros.items():
    if w < 4 or w > 14 or n < 20 or pos.get(pid) not in ("RB", "WR", "TE", "QB"): continue
    nw = ros.get((y, w + 1, pid), 0)
    dr = drops[(y, w + 1, pid)] / n; u = snaps(y, w + 1, pid); f = fut(y, w + 1, pid)
    if f[0] is None or u is None: continue
    grp = "mass-dropped" if dr >= .1 else "kept"
    G[(grp, u)].append(f)
fa = collections.Counter()
for l in R.values(): fa[l["season"]] += 1
for (y, w, pid), n in adds.items():
    if w < 4 or w > 14 or pos.get(pid) not in ("RB", "WR", "TE", "QB"): continue
    if n / fa[y] >= .1:
        u = snaps(y, w, pid); f = fut(y, w, pid)
        if f[0] is not None and u: G[("mass-added", u)].append(f)
for k in sorted(G):
    xs = G[k]
    print("%-13s usage %-6s n %5d  real-minus-projection %+.2f pts/game  (real %.1f, proj %.1f)" % (k[0], k[1], len(xs), st.mean(x[0] for x in xs), st.mean(x[1] for x in xs), st.mean(x[2] for x in xs)))
