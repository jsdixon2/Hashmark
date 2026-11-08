"""Keeper trades vs what actually happened (bt/keepers.json.gz).
Outcome for each side of a trade, in fantasy points:
  now    = how much its best lineup gained over the rest of that season (real weekly rosters, real points, league scoring)
  future = next season: players it got in the deal and then kept, minus players it gave and the other team kept,
           each worth (points above replacement next season) − (what a normal pick in the keeper's round produced in that draft)
Predictions made with what was known that week; fit how much the future should count (by keepers per roster spot)."""
import json, gzip, os, sys, numpy as np, pandas as pd, collections, itertools, pickle
B = os.path.dirname(os.path.abspath(__file__)); H = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bt")
K = json.load(gzip.open(f"{H}/keepers.json.gz", "rt"))["pairs"]
ST = json.load(gzip.open(f"{H}/sleeper_stats.json.gz", "rt"))["w"]
PJ = json.load(gzip.open(f"{H}/sleeper_proj.json.gz", "rt"))["w"]
HV = json.load(gzip.open(f"{H}/hv.json.gz", "rt")); HMS = [pd.Timestamp(d).value // 10**6 for d in HV["d"]]
ids = pd.read_csv(B + "/dl/ids.csv", low_memory=False)[["sleeper_id", "position", "birthdate"]].dropna(subset=["sleeper_id"])
ids["sleeper_id"] = ids.sleeper_id.astype(str).str.replace(r"\.0$", "", regex=True); POS = dict(zip(ids.sleeper_id, ids.position))
for w in PJ.values():
    for pid, s in w.items():
        if s.get("pos") and pid not in POS: POS[pid] = s["pos"]
OFF = {"QB", "RB", "WR", "TE"}
ELIG = {"QB": {"QB"}, "RB": {"RB"}, "WR": {"WR"}, "TE": {"TE"}, "FLEX": {"RB", "WR", "TE"}, "WRRB_FLEX": {"RB", "WR"}, "REC_FLEX": {"WR", "TE"}, "SUPER_FLEX": OFF}
REPL = {"QB": 14, "RB": 9, "WR": 9, "TE": 7}
def score(s, sc, pos):
    if not s: return 0.0
    v = sum(s[k] * sc[k] for k in sc if k in s and not k.startswith("bonus"))
    if "pass_int" in s and "pass_int" not in sc: v -= s["pass_int"]
    if pos in ("TE", "RB", "WR") and s.get("rec"): v += s["rec"] * sc.get("bonus_rec_" + pos.lower(), 0)
    return v
def opt(players, val, slots):
    pool = sorted([p for p in players if POS.get(p) in OFF], key=lambda p: -val(p)); used = set(); s = 0.0
    for sl in sorted([x for x in slots if x in ELIG], key=lambda x: len(ELIG[x])):
        for p in pool:
            if p not in used and POS[p] in ELIG[sl]: used.add(p); s += max(0.0, val(p)); break
    return s
def hvv(t, di, pid, sf):
    m = HV.setdefault("_m", {}).get((t, di))
    if m is None: m = {HV["ids"][ix]: i + 1 for i, ix in enumerate(HV["t"][t][di])}; HV["_m"][(t, di)] = m
    r = m.get(pid); A = np.array([[1, 10000], [12, 7677], [24, 6028], [50, 3762], [100, 1664], [150, 782], [200, 381], [300, 98], [450, 14]], float)
    return float(np.exp(np.interp(np.log(r or 400), np.log(A[:, 0]), np.log(A[:, 1]))))
rows = []
for key, pr in K.items():
    L, N = pr["s"], pr["next"]; season = L["season"]; sc = L["sc"] or {"rec": 1, "pass_td": 4, "pass_yd": .04, "rush_yd": .1, "rec_yd": .1, "rush_td": 6, "rec_td": 6, "fum_lost": -2}
    slots = L["pos"] or []; n = L["n"] or 12; sf = "SUPER_FLEX" in slots or slots.count("QB") > 1
    weeks = {int(w): v for w, v in (L["weeks"] or {}).items()}; last = max(weeks) if weeks else 0
    if not weeks or not N.get("draft"): continue
    kmax = N.get("max_keepers") or L.get("max_keepers") or 0
    cap = len([s for s in slots if s not in ("IR", "TAXI")]) or 16
    # next season: who kept whom, keeper rounds; non-keeper pick production by round = cost of a keeper in that round
    nd = N["draft"]; ns = N["season"]
    def ppg_season(pid, y):
        pts = [score(ST.get(f"{y}-{w}", {}).get(pid), sc, POS.get(pid)) for w in range(1, 18) if (ST.get(f"{y}-{w}", {}).get(pid) or {}).get("gp")]
        return (np.mean(pts), len(pts)) if pts else (0.0, 0)
    def par_next(pid):
        if POS.get(pid) not in OFF: return 0.0
        m, g = ppg_season(pid, ns); return max(0.0, m - REPL[POS[pid]]) * g * (17 / 9 if ns == 2026 else 1)
    kept = {}; rnd = collections.defaultdict(list)
    for r, no, pid, rid, kp, slot, amt in nd["picks"]:
        if not pid: continue
        if kp: kept[str(pid)] = (rid, r)
        else: rnd[r].append(par_next(str(pid)))
    rcost = {r: float(np.mean(v)) for r, v in rnd.items() if v}
    lastr = max(rcost) if rcost else 16
    def cost(r): return rcost.get(r, rcost.get(lastr, 0.0))
    # keeper cost style of this league: do keepers sit in their old draft round?
    od = {str(p[2]): p[0] for p in (L.get("draft") or {}).get("picks", []) if p[2]}
    same = [abs(kept[p][1] - od[p]) <= 1 for p in kept if p in od]; style = "round" if same and np.mean(same) > .6 else "none"
    # weekly rosters and points
    rost = {w: {r[0]: set(map(str, r[4] or [])) for r in v} for w, v in weeks.items()}
    def pts(pid, w): return score(ST.get(f"{season}-{w}", {}).get(pid), sc, POS.get(pid))
    def proj(pid, w):
        p = [score(PJ.get(f"{season}-{x}", {}).get(pid), sc, POS.get(pid)) for x in (w, w + 1)]; p = [x for x in p if x]
        sofar = [pts(pid, x) for x in range(1, w) if (ST.get(f"{season}-{x}", {}).get(pid) or {}).get("gp")]
        a = np.mean(p) if p else 0.0
        return .5 * a + .5 * np.mean(sofar) if len(sofar) >= 2 else a
    for t in L["tx"]:
        typ, wk, rids, adds, drops, picks, faab, bid, ts = t
        if typ != "trade" or len(rids) != 2 or not adds or picks: continue
        if not all(POS.get(p) in OFF for p in adds): continue
        w0 = max(1, wk); post_w = [w for w in sorted(rost) if w > w0 and w < (L.get("pws") or 15) + 3]
        if w0 not in rost and (w0 - 1) not in rost: continue
        R0 = rost.get(w0) or rost.get(w0 - 1)
        side = {}
        for r in rids:
            got = [p for p, rr in adds.items() if rr == r]; gave = [p for p, rr in adds.items() if rr != r and drops.get(p) == r]
            base = set(R0.get(r, set())); pre = (base | set(gave)) - set(got); post = (pre - set(gave)) | set(got)
            now = sum(opt(post, lambda p: pts(p, w), slots) - opt(pre, lambda p: pts(p, w), slots) for w in post_w)
            pnow = opt(post, lambda p: proj(p, w0), slots) - opt(pre, lambda p: proj(p, w0), slots)
            side[r] = dict(got=got, gave=gave, now=now, pnow=pnow, pre=pre, post=post)
        a, b = rids
        for r, o in ((a, b), (b, a)):
            s, so = side[r], side[o]
            fut = sum(par_next(p) - cost(kept[p][1]) for p in s["got"] if p in kept and kept[p][0] == r) - sum(par_next(p) - cost(kept[p][1]) for p in s["gave"] if p in kept and kept[p][0] == o)
            side[r]["fut"] = fut
        pf = collections.Counter()
        for w in weeks:
            if w <= w0:
                for row in weeks[w]: pf[row[0]] += row[2]
        order = sorted(pf, key=lambda x: -pf[x]); prk = {x: (order.index(x) + 1) / max(1, len(order)) for x in order}
        di = max([i for i, m in enumerate(HMS) if m <= (ts or 0)], default=None)
        if di is None: continue
        rows.append(dict(key=key, season=season, wk=wk, n=n, kmax=kmax, cap=cap, kshare=min(1, kmax / cap) if cap else 0, style=style, rem=len(post_w),
                         a=a, b=b, side={r: {k: v for k, v in side[r].items() if k not in ("pre", "post")} for r in rids},
                         pre={r: list(side[r]["pre"]) for r in rids}, post={r: list(side[r]["post"]) for r in rids}, di=di, sf=sf,
                         rcost=rcost, lastr=lastr, prk={r: prk.get(r, .5) for r in rids}, od={p: od.get(p) for r in rids for p in side[r]["post"] | side[r]["pre"]}))
print(len(rows), "keeper trades", collections.Counter(r["style"] for r in rows), collections.Counter(r["season"] for r in rows))
pickle.dump(rows, open(B + "/e7_rows.pkl", "wb"))
