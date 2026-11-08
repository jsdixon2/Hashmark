"""Team-level waiver test: for every team in every rebuilt redraft league each week, pick the one add each method recommends
(dropping that method's least useful bench player) and measure the real lineup points it added over the next 4 weeks."""
import json, gzip, os, collections, numpy as np, pandas as pd, pickle
B = os.path.dirname(os.path.abspath(__file__)); H = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bt")
ST = json.load(gzip.open(f"{H}/sleeper_stats.json.gz", "rt"))["w"]
D = pd.read_pickle(B + "/e9_Dfit.pkl")
L = json.load(gzip.open(f"{H}/leagues.json.gz", "rt"))["leagues"]
G = pd.read_csv(B + "/dl/games.csv", low_memory=False); G = G[G.game_type == "REG"]
OFF = ("QB", "RB", "WR", "TE")
ELIG = {"QB": {"QB"}, "RB": {"RB"}, "WR": {"WR"}, "TE": {"TE"}, "FLEX": {"RB", "WR", "TE"}, "WRRB_FLEX": {"RB", "WR"}, "REC_FLEX": {"WR", "TE"}, "SUPER_FLEX": set(OFF)}
SEAS = [int(x) for x in os.environ.get("SEAS", "2024,2025").split(",")]
APP = {}; pred = {}; posd = {}; projd = {}; ownd = {}
for r in D[D.s.isin(SEAS)].itertuples():
    APP[(r.s, r.w, r.pid)] = (.62 * (r.ppg if r.gp > 0 else r.proj) + .38 * r.proj) if r.gp > 0 else r.proj
    pred[(r.s, r.w, r.pid)] = max(0.0, r.lin); posd[r.pid] = r.pos; projd[(r.s, r.w, r.pid)] = r.proj; ownd[(r.s, r.w, r.pid)] = r.own
def actual(s, k, pid, key):
    st = ST.get(f"{s}-{k}", {}).get(pid)
    return (st or {}).get(key, 0.0) if st else 0.0
def opt(players, val, slots):
    pool = sorted(players, key=lambda p: -val(p)); used = set(); tot = 0.0
    for sl in sorted(slots, key=lambda x: len(ELIG[x])):
        for p in pool:
            if p not in used and posd.get(p) in ELIG[sl]: used.add(p); tot += max(0.0, val(p)); break
    return tot
res = collections.defaultdict(list); nteam = 0
for lg in L.values():
    s = lg["season"]
    if s not in SEAS or lg.get("type") not in (0, None) or not lg.get("draft") or not lg["draft"].get("picks"): continue
    slots = [x for x in (lg.get("pos") or []) if x in ELIG]
    if not slots: continue
    rec = (lg.get("sc") or {}).get("rec", 1); key = "pts_ppr" if rec >= .75 else "pts_half_ppr" if rec >= .25 else "pts_std"
    ro = {}
    for p in lg["draft"]["picks"]:
        if p[2]: ro[str(p[2])] = p[3]
    tx = sorted(lg.get("tx") or [], key=lambda t: (t[1], t[8] or 0)); i = 0
    for w in range(1, 14):
        while i < len(tx) and tx[i][1] < w:
            t = tx[i]
            for pid in (t[4] or {}): ro.pop(str(pid), None)
            for pid, rid in (t[3] or {}).items(): ro[str(pid)] = rid
            i += 1
        if w < 3: continue
        avail = [pid for (ss, ww, pid) in pred if ss == s and ww == w and pid not in ro] if False else None
        if avail is None:
            avail = [pid for pid in posd if (s, w, pid) in pred and pid not in ro]
        teams = collections.defaultdict(list)
        for pid, rid in ro.items():
            if posd.get(pid) in OFF: teams[rid].append(pid)
        ks = range(w + 1, min(w + 4, 18))
        for rid, mine in teams.items():
            if len(mine) < len(slots): continue
            nteam += 1
            pr = lambda p: pred.get((s, w, p), 0.0)
            base_act = sum(opt(mine, lambda p: actual(s, k, p, key), slots) for k in ks)
            def realized(add, drop):
                new = [p for p in mine if p != drop] + [add]
                return sum(opt(new, lambda p: actual(s, k, p, key), slots) for k in ks) - base_act
            def worst_bench(val):
                st = set(); pool = sorted(mine, key=lambda p: -val(p)); used = set()
                for sl in sorted(slots, key=lambda x: len(ELIG[x])):
                    for p in pool:
                        if p not in used and posd.get(p) in ELIG[sl]: used.add(p); break
                bench = [p for p in mine if p not in used]
                return min(bench, key=val) if bench else min(mine, key=val)
            meths = {
                "Sleeper projection, best available": (lambda p: projd.get((s, w, p), 0.0), "raw"),
                "Crowd: most-rostered available": (lambda p: ownd.get((s, w, p), 0.0), "raw"),
                "Fitted score, best available": (pr, "raw"),
                "Hashmark before (PPG+projection blend), best available": (lambda p: APP.get((s, w, p), 0.0), "raw"),
                "Fitted score, biggest lift to this lineup": (pr, "lineup"),
                "Sleeper projection, biggest lift to this lineup": (lambda p: projd.get((s, w, p), 0.0), "lineup"),
            }
            top = sorted(avail, key=lambda p: -pr(p))[:25]; topj = sorted(avail, key=lambda p: -projd.get((s, w, p), 0.0))[:25]
            for nm, (val, how) in meths.items():
                drop = worst_bench(val)
                if how == "raw": add = max(avail, key=val)
                else:
                    base = opt([p for p in mine if p != drop], val, slots)
                    cand = top if val is pr else topj
                    add = max(cand, key=lambda p: opt([x for x in mine if x != drop] + [p], val, slots) - base)
                res[nm].append(realized(add, drop))
out = {"teams_weeks": nteam}
for k, v in res.items(): v = np.array(v); out[k] = dict(mean_gain=round(float(v.mean()), 2), helped=round(float((v > 0).mean()), 3), hurt=round(float((v < 0).mean()), 3))
print(json.dumps(out, indent=1)); json.dump(out, open(B + "/e9_team.json", "w"), indent=1)
