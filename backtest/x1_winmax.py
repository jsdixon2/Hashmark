"""Edge test 1: lineups set for win probability instead of projected points.
Archive bt/rosters.json.gz (900 real leagues 2022-25, weekly starters + full rosters + matchup ids). Projection = Sleeper's
(bt/sleeper_proj) in the league's catch scoring; actual = Sleeper stat line points. K/DEF kept as the manager started them.
Per player sd = a+b*proj per position, residual correlations by position pair for same-team and opposing-team players:
fitted on 2022-23, tested on 2024-25. Baseline = max-projection lineup for both teams. Win-max = up to 2 swaps of a bench
player into a slot when it raises P(win) (normal approx vs opponent's max-projection lineup) by >= MIN. Scored on real wins."""
import gzip, json, csv, math, collections, itertools, sys, statistics as st
ELIG = {"QB": {"QB"}, "RB": {"RB"}, "WR": {"WR"}, "TE": {"TE"}, "FLEX": {"RB", "WR", "TE"}, "WRRB_FLEX": {"RB", "WR"},
        "REC_FLEX": {"WR", "TE"}, "SUPER_FLEX": {"QB", "RB", "WR", "TE"}}
R = json.load(gzip.open("bt/rosters.json.gz", "rt"))["leagues"]
SP = json.load(gzip.open("bt/sleeper_proj.json.gz", "rt"))["w"]; ST = json.load(gzip.open("bt/sleeper_stats.json.gz", "rt"))["w"]
ids = {}; g2s = {}
for r in csv.DictReader(open("backtest/dl/ids.csv", encoding="utf-8")):
    s = str(r.get("sleeper_id") or "").split(".")[0]
    if s not in ("", "NA"): ids[s] = r.get("position"); g2s[r.get("gsis_id")] = s
TM = {}
for y in range(2022, 2026):
    for r in csv.DictReader(open(f"backtest/dl/pw_{y}.csv", encoding="utf-8")):
        if r["season_type"] == "REG" and r["player_id"] in g2s: TM[(y, int(r["week"]), g2s[r["player_id"]])] = (r["team"], r["opponent_team"])
KEY = {1: "pts_ppr", .5: "pts_half_ppr", 0: "pts_std"}
def pk(l): rec = l["sc"].get("rec", 0); return KEY.get(rec, "pts_ppr" if rec > .75 else "pts_half_ppr" if rec > .25 else "pts_std")
# 1) residual model on 2022-23 player-weeks
res = collections.defaultdict(list); byg = collections.defaultdict(list)
for k in SP:
    y, w = map(int, k.split("-"))
    if y not in (2022, 2023): continue
    for pid, pr in SP[k].items():
        pos = ids.get(pid); p = pr.get("pts_ppr") or 0; s = ST.get(k, {}).get(pid)
        if pos not in ("QB", "RB", "WR", "TE") or p < 2 or not s or not s.get("gp"): continue
        e = (s.get("pts_ppr") or 0) - p; res[pos].append((p, e)); t = TM.get((y, w, pid))
        if t: byg[(y, w, t[0], t[1])].append((pos, e / max(3, 2.5 + .45 * p)))
SDM = {}
for pos, xs in res.items():  # fit |e|*sqrt(pi/2) ~ a + b p
    X = [p for p, e in xs]; Y = [abs(e) * 1.2533 for p, e in xs]; mx, my = st.mean(X), st.mean(Y)
    b = sum((x - mx) * (y - my) for x, y in zip(X, Y)) / sum((x - mx) ** 2 for x in X); SDM[pos] = (my - b * mx, b)
C = collections.defaultdict(lambda: [0, 0, 0, 0, 0])
for (y, w, t, o), xs in byg.items():
    opp = byg.get((y, w, o, t), [])
    for (a, ea), (b, eb) in itertools.combinations(xs, 2):
        for kk in ((("s",) + tuple(sorted((a, b)))),): c = C[kk]; c[0] += 1; c[1] += ea * eb; c[2] += ea * ea; c[3] += eb * eb
    for a, ea in xs:
        for b, eb in opp:
            if a <= b: c = C[("o", a, b)]; c[0] += 1; c[1] += ea * eb; c[2] += ea * ea; c[3] += eb * eb
CORR = {k: v[1] / math.sqrt(v[2] * v[3]) for k, v in C.items() if v[0] > 200}
print("sd", {k: (round(a, 2), round(b, 3)) for k, (a, b) in SDM.items()}); print("corr", {"|".join(k): round(v, 3) for k, v in sorted(CORR.items())})
def sd(pos, p): a, b = SDM[pos]; return max(1.5, a + b * p)
def corr(side, a, b):
    k = (side,) + tuple(sorted((a, b))); return CORR.get(k, 0)
def best(roster, slots, P):
    pool = sorted([x for x in roster if ids.get(x) in ("QB", "RB", "WR", "TE")], key=lambda x: -P.get(x, 0)); used = set(); out = []
    for s in sorted(slots, key=lambda s: len(ELIG[s])):
        c = next((x for x in pool if x not in used and ids[x] in ELIG[s]), None)
        if c: used.add(c)
        out.append((s, c))
    return out
def pwin(A, B, P, y, w, kdA, kdB):
    mA = sum(P.get(x, 0) for x in A) + kdA; mB = sum(P.get(x, 0) for x in B) + kdB
    items = [(x, 1) for x in A] + [(x, -1) for x in B]; v = 2 * 7.0 ** 2  # K/DEF variance both sides
    sds = {x: sd(ids[x], P.get(x, 0)) for x, _ in items}; v += sum(sds[x] ** 2 for x, _ in items)
    for (x, sx), (z, sz) in itertools.combinations(items, 2):
        tx, tz = TM.get((y, w, x)), TM.get((y, w, z))
        if not tx or not tz: continue
        side = "s" if tx[0] == tz[0] else "o" if tx[0] == tz[1] else None
        if side: v += 2 * sx * sz * corr(side, ids[x], ids[z]) * sds[x] * sds[z]
    return 0.5 * (1 + math.erf((mA - mB) / math.sqrt(2 * v)))
MIN = float(sys.argv[1]) if len(sys.argv) > 1 else .01
out = collections.defaultdict(lambda: [0, 0, 0, 0.0, 0.0, 0.0])  # n changed, wins base, wins opt, pts base, pts opt, said gain
nall = collections.Counter()
for l in R.values():
    y = l["season"]
    if y < 2024: continue
    slots = [s for s in l["pos"] if s in ELIG]; K = pk(l)
    for wk, ms in l["weeks"].items():
        w = int(wk); k = f"{y}-{w}"
        if w > l.get("pws", 15) - 1 or k not in SP: continue
        P = {pid: (pr.get(K) or 0) for pid, pr in SP[k].items()}; A = {pid: ((s.get(K) or 0) if s.get("gp") else 0) for pid, s in ST.get(k, {}).items()}
        bym = collections.defaultdict(list)
        for t in ms: bym[t[1]].append(t)
        for pair in bym.values():
            if len(pair) != 2: continue
            L = []
            for t in pair:
                kd = [x for x in t[3] if ids.get(x) not in ("QB", "RB", "WR", "TE")]
                L.append((best(t[4], slots, P), sum(P.get(x, 0) for x in kd), sum(A.get(x, 0) for x in kd), t[4]))
            for i in (0, 1):
                me, op = L[i], L[1 - i]; Ab = [x for s, x in me[0] if x]; Bb = [x for s, x in op[0] if x]
                base = pwin(Ab, Bb, P, y, w, me[1], op[1]); cur = list(me[0]); pcur = base
                for _ in range(2):
                    bestc = None
                    used = {x for s, x in cur if x}
                    for j, (s, x) in enumerate(cur):
                        for z in me[3]:
                            if z in used or ids.get(z) not in ELIG[s] or P.get(z, 0) < 1: continue
                            c2 = cur[:]; c2[j] = (s, z); pw_ = pwin([q for _, q in c2 if q], Bb, P, y, w, me[1], op[1])
                            if pw_ > pcur + MIN and (not bestc or pw_ > bestc[0]): bestc = (pw_, c2)
                    if not bestc: break
                    pcur, cur = bestc
                nall[base < .5] += 1
                if cur == me[0]: continue
                oppA = sum(A.get(x, 0) for x in Bb) + op[2]
                pb = sum(A.get(x, 0) for x in Ab) + me[2]; po = sum(A.get(x, 0) for x, in [(q,) for _, q in cur if q]) + me[2]
                o = out[("dog" if base < .5 else "fav", y)]; o[0] += 1; o[1] += pb > oppA; o[2] += po > oppA; o[3] += pb; o[4] += po; o[5] += pcur - base
print("team-games", dict(nall))
for k in sorted(out):
    n, wb, wo, pb, po, g = out[k]
    print(k, "changed", n, "won base %.3f opt %.3f" % (wb / n, wo / n), "net wins", wo - wb, "said +%.3f" % (g / n), "pts %+.2f" % ((po - pb) / n))
