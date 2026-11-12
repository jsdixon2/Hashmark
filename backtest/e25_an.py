"""Analysis of e25_trades.pkl (backtest/e25_data.py): calibration of the shipped trade grade (effV TC + pvTable PVT) on
real trades, 2021-24 (the original fit's seasons) vs 2025 (hold-out); young-player / consolidation / picks splits;
v118-style young-player value bump; IDP vs offense with a production proxy. Writes backtest/e25.json."""
import os, json, numpy as np, pandas as pd
B = os.path.dirname(os.path.abspath(__file__))
D = pd.read_pickle(B + "/e25_trades.pkl")
PVT = [[0, .5], [.05, .54], [.12, .58], [.2, .605], [.3, .63], [.45, .65], [.6, .675], [.75, .7], [.9, .765], [1, .78]]
X0, Y0 = np.array([p[0] for p in PVT]), np.array([p[1] for p in PVT])
def pv(pct, Y=Y0):
    a = min(1.0, abs(pct)); v = float(np.interp(a, X0, Y)); return v if pct >= 0 else 1 - v
def effV(vs, d=.75, g=1.3):
    v = sorted([x for x in vs if x > 0], reverse=True); s = sum(d ** i * x ** g for i, x in enumerate(v))
    return s ** (1 / g) if s > 0 else 0.0
def young_w(a): return 0.0 if a is None else 1.0 if a <= 23 else 0.0 if a >= 26 else (26 - a) / 3
def gaps(vA, vB, agA=None, agB=None, k=0.0, d=.75, g=1.3):
    if k:
        vA = [v * (1 + k * young_w(a)) for v, a in zip(vA, agA + [None] * (len(vA) - len(agA)))]
        vB = [v * (1 + k * young_w(a)) for v, a in zip(vB, agB + [None] * (len(vB) - len(agB)))]
    a, b = effV(vA, d, g), effV(vB, d, g)
    return (a - b) / max(1, a, b), a + b
# player values come first in vA/vB (players then picks, in the order the data script stored them) -> ages align
def build(k=0.0, d=.75, g=1.3, out="o9"):
    R = []
    for r in D.itertuples():
        y = getattr(r, out)
        if y is None or (isinstance(y, float) and np.isnan(y)) or y == 0: continue
        pct, tot = gaps(r.vA, r.vB, r.agA, r.agB, k, d, g)
        if tot < 60: continue
        R.append((pct, 1 if y > 0 else 0))
    return R
D["pidx"] = range(len(D))
young = lambda r: any(a is not None and a <= 23 for a in list(r.agA) + list(r.agB))
D["young"] = [young(r) for r in D.itertuples()]
D["cons"] = [len(r.vA) != len(r.vB) for r in D.itertuples()]
D["picks"] = (D.npkA + D.npkB) > 0
D["idp"] = (D.idpA + D.idpB) > 0
D["grp"] = np.where(D.s <= 2024, "2021-24", np.where(D.s == 2025, "2025", "2026"))
def score(m, Y=Y0, k=0.0, d=.75, g=1.3, out="o9", P=None):
    """calibration of the favoured side: bins by stated P, won share; accuracy, Brier"""
    rows = []
    for r in D[m].itertuples():
        y = getattr(r, out)
        if y is None or (isinstance(y, float) and np.isnan(y)) or y == 0: continue
        if P is None:
            pct, tot = gaps(r.vA, r.vB, r.agA, r.agB, k, d, g)
            if tot < 60: continue
            p = pv(pct, Y)
        else:
            p = P(r)
            if p is None: continue
        won = 1 if y > 0 else 0
        if p < .5: p, won = 1 - p, 1 - won
        rows.append((p, won))
    if not rows: return dict(n=0)
    a = np.array(rows); o = dict(n=len(a), said=round(float(a[:, 0].mean()), 3), won=round(float(a[:, 1].mean()), 3),
                                brier=round(float(((a[:, 0] - a[:, 1]) ** 2).mean()), 4))
    for lo, hi, lab in [(.5, .55, "50-55"), (.55, .65, "60"), (.65, .75, "70"), (.75, 1.01, "80")]:
        q = a[(a[:, 0] >= lo) & (a[:, 0] < hi)]
        o[lab] = dict(n=len(q), said=round(float(q[:, 0].mean()), 3) if len(q) else None, won=round(float(q[:, 1].mean()), 3) if len(q) else None)
    return o
def line(lab, o):
    if not o.get("n"): return f"  {lab:34s} n=0"
    b = " | ".join(f"{k}: {o[k]['won']:.0%} of {o[k]['n']} (said {o[k]['said']:.0%})" if o[k]["n"] else f"{k}: -" for k in ("50-55", "60", "70", "80"))
    return f"  {lab:34s} n={o['n']:5d} said {o['said']:.1%} won {o['won']:.1%} brier {o['brier']:.4f} || {b}"
OFFm = ~D.idp
res = {}
print("1) shipped grade (TC .75/1.3 + PVT), outcome = PAR rest of season + next season wk1-9, favoured side")
for g_ in ("2021-24", "2025", "2026"):
    for lab, m in [("all", OFFm), ("dynasty", OFFm & (D.ty == 2)), ("keeper", OFFm & (D.ty == 1)), ("player <=23 involved", OFFm & D.young),
                   ("no player <=23", OFFm & ~D.young), ("consolidation (unequal counts)", OFFm & D.cons), ("with picks", OFFm & D.picks),
                   ("players only", OFFm & ~D.picks), ("SF", OFFm & D.sf), ("1QB", OFFm & ~D.sf)]:
        o = score(m & (D.grp == g_)); res[f"{g_}|{lab}"] = o; print(line(f"{g_} {lab}", o))
    print()
o = score(OFFm & (D.grp == "2021-24"), out="oF"); res["2021-24|all|HF"] = o; print(line("2021-24 all, through all next season", o))
# miscalibration check on the hold-out: |won - said| in any bin with n >= 200
flag = []
for k, o in res.items():
    if not k.startswith("2025") or not o.get("n"): continue
    for b in ("50-55", "60", "70", "80"):
        if o[b]["n"] >= 200 and abs(o[b]["won"] - o[b]["said"]) > .03: flag.append((k, b, o[b]))
print("\nhold-out bins off by > 3 pts with n >= 200:", flag or "none")
res["holdout_flags"] = [dict(split=k, bin=b, **v) for k, b, v in flag]
print("\n2) v118-style young-player bump on the replayed values (x (1 + k*w), w = 1 at <= 23 fading to 0 at 26)")
yb = {}
for k in (0, .02, .05, .08):
    for g_ in ("2021-24", "2025"):
        o = score(OFFm & D.young & (D.grp == g_), k=k); yb[f"k{k}|{g_}"] = o
        print(f"  k={k:.2f} {g_} young trades n={o['n']} said {o['said']:.1%} won {o['won']:.1%} brier {o['brier']:.4f}")
res["young_bump"] = yb
print("\n3) TC grid on 2021-24 (Brier), checked on 2025")
best = []
for d in (.6, .7, .75, .8, .9):
    for g in (1.0, 1.15, 1.3, 1.5):
        a = score(OFFm & (D.grp == "2021-24"), d=d, g=g); b = score(OFFm & (D.grp == "2025"), d=d, g=g)
        best.append((a["brier"], d, g, b["brier"], a["won"], b["won"]))
best.sort()
for x in best[:5]: print(f"  d={x[1]} g={x[2]}: 2021-24 brier {x[0]:.4f} acc {x[4]:.1%} | 2025 brier {x[3]:.4f} acc {x[5]:.1%}")
sh = [x for x in best if x[1] == .75 and x[2] == 1.3][0]; print(f"  shipped d=.75 g=1.3: 2021-24 {sh[0]:.4f} / 2025 {sh[3]:.4f}")
res["tc_grid_top"] = [dict(d=x[1], g=x[2], brier_fit=x[0], brier_2025=x[3]) for x in best[:5]]; res["tc_shipped"] = dict(brier_fit=sh[0], brier_2025=sh[3])
print("\n4) IDP vs offense, production proxy (PAR per game at the time; same effV + PVT), IDP leagues")
def Pprod(r):
    a, b = effV(r.ppA), effV(r.ppB)
    if a + b <= 0 or r.npkA + r.npkB: return None
    return pv((a - b) / max(1e-9, a, b))
def Pecr(r):
    pct, tot = gaps(r.vA, r.vB)
    return None if tot < 60 or r.npkA + r.npkB else pv(pct)
idr = {}
for lab, m in [("IDP trades (IDP leagues)", D.idp), ("offense-only trades, IDP leagues", D.idl & ~D.idp), ("offense-only trades, all leagues", ~D.idp)]:
    for gl, gm in [("2021-24", D.s <= 2024), ("2025-26", D.s >= 2025), ("all", D.s > 0)]:
        o = score(m & gm, P=Pprod); idr[f"{lab}|{gl}|prod"] = o; print(line(f"{lab[:22]} {gl} prod", o))
    o = score(m, P=Pecr); idr[f"{lab}|all|ecr"] = o; print(line(f"{lab[:22]} all ECR(app)", o))
res["idp"] = idr
print("\n2b) young bump on longer horizons (values are long-term; H9 is short): 2021-24 through next season, 2021-23 through 2 more")
for k in (0, .02, .05, .08):
    a1 = score(OFFm & D.young & (D.grp == "2021-24"), k=k, out="oF"); a2 = score(OFFm & D.young & (D.s <= 2023), k=k, out="oL")
    yb[f"k{k}|HF"] = a1; yb[f"k{k}|HL"] = a2
    print(f"  k={k:.2f} next season: n={a1['n']} won {a1['won']:.1%} brier {a1['brier']:.4f} | two more seasons: n={a2['n']} won {a2['won']:.1%} brier {a2['brier']:.4f}")
print("\n3b) TC grid robustness: players-only trades and longer horizons (Brier, shipped PVT)")
rob = {}
for d, g in [(.75, 1.3), (.9, 1.0), (.8, 1.0), (.9, 1.15), (.75, 1.0)]:
    r_ = dict(po_fit=score(OFFm & ~D.picks & (D.grp == "2021-24"), d=d, g=g)["brier"], po_2025=score(OFFm & ~D.picks & (D.grp == "2025"), d=d, g=g)["brier"],
              HF=score(OFFm & (D.grp == "2021-24"), d=d, g=g, out="oF")["brier"], HL=score(OFFm & (D.s <= 2023), d=d, g=g, out="oL")["brier"],
              y2025=score(OFFm & D.young & (D.grp == "2025"), d=d, g=g)["brier"], cons2025=score(OFFm & D.cons & (D.grp == "2025"), d=d, g=g)["brier"])
    rob[f"{d}/{g}"] = r_; print(f"  d={d} g={g}: " + " ".join(f"{k} {v:.4f}" for k, v in r_.items()))
res["tc_robust"] = rob
print("\n5) refit: TC (d, g) and P = .5 + A*tanh(|gap|/c) by Brier on 2021-24, then 2025 hold-out")
def rows_(m, d, g, out="o9"):
    R = []
    for r in D[m].itertuples():
        y = getattr(r, out)
        if y is None or (isinstance(y, float) and np.isnan(y)) or y == 0: continue
        pct, tot = gaps(r.vA, r.vB, d=d, g=g)
        if tot < 60: continue
        R.append((abs(pct), 1 if (y > 0) == (pct >= 0) else 0))
    return np.array(R)
fit = []
for d in (.7, .75, .8, .85, .9, .95, 1.0):
    for g in (.9, 1.0, 1.1, 1.2, 1.3):
        R = rows_(OFFm & (D.grp == "2021-24"), d, g)
        for A in np.arange(.1, .36, .01):
            for c in (.1, .15, .2, .25, .3, .4, .5, .7):
                p = .5 + A * np.tanh(R[:, 0] / c); fit.append((float(((p - R[:, 1]) ** 2).mean()), d, g, round(float(A), 2), c))
fit.sort(); bf = fit[0]; print("  best on 2021-24:", bf)
_, d1, g1, A1, c1 = bf
def Pnew(r, d=d1, g=g1, A=A1, c=c1):
    pct, tot = gaps(r.vA, r.vB, d=d, g=g)
    if tot < 60: return None
    v = .5 + A * np.tanh(abs(pct) / c); return v if pct >= 0 else 1 - v
cmp = {}
for lab, m in [("all", OFFm), ("player <=23", OFFm & D.young), ("consolidation", OFFm & D.cons), ("with picks", OFFm & D.picks), ("players only", OFFm & ~D.picks), ("SF", OFFm & D.sf), ("1QB", OFFm & ~D.sf)]:
    for g_ in ("2025", "2026"):
        o0 = score(m & (D.grp == g_)); o1 = score(m & (D.grp == g_), P=Pnew); cmp[f"{g_}|{lab}"] = dict(shipped=o0, refit=o1)
        print(line(f"{g_} {lab} shipped", o0)); print(line(f"{g_} {lab} refit", o1))
for lab, m, out in [("2021-24 next season", OFFm & (D.grp == "2021-24"), "oF"), ("2021-23 two more seasons", OFFm & (D.s <= 2023), "oL")]:
    o0 = score(m, out=out); o1 = score(m, P=Pnew, out=out); cmp[lab] = dict(shipped=o0, refit=o1); print(line(lab + " shipped", o0)); print(line(lab + " refit", o1))
res["refit"] = dict(d=d1, g=g1, A=A1, c=c1, brier_fit=bf[0], compare=cmp)
print("\n6) candidate: d .9 / g 1.0 with the shipped PVT, and with PVT refit (isotonic at the PVT knots on 2021-24)")
def iso_pvt(d, g):
    R = rows_(OFFm & (D.grp == "2021-24"), d, g); Y = []
    for i, x in enumerate(X0):
        lo = (X0[i - 1] + x) / 2 if i else 0; hi = (X0[i + 1] + x) / 2 if i + 1 < len(X0) else 9
        q = R[(R[:, 0] >= lo) & (R[:, 0] < hi)]; Y.append(float(q[:, 1].mean()) if len(q) >= 30 else None)
    Y[0] = .5; last = .5
    for i in range(len(Y)):
        if Y[i] is None: Y[i] = last
        Y[i] = max(last, Y[i]); last = Y[i]
    return np.round(np.array(Y), 3)
Y9 = iso_pvt(.9, 1.0); print("  PVT refit at knots", list(X0), "->", list(Y9))
cand = {"shipped": dict(d=.75, g=1.3, Y=Y0), "d.9 g1 PVT": dict(d=.9, g=1.0, Y=Y0), "d.9 g1 PVT refit": dict(d=.9, g=1.0, Y=Y9)}
c6 = {}
for lab, m, out in [("2025 all", OFFm & (D.grp == "2025"), "o9"), ("2025 players only", OFFm & ~D.picks & (D.grp == "2025"), "o9"), ("2025 with picks", OFFm & D.picks & (D.grp == "2025"), "o9"),
                    ("2025 player <=23", OFFm & D.young & (D.grp == "2025"), "o9"), ("2025 consolidation", OFFm & D.cons & (D.grp == "2025"), "o9"),
                    ("2026 all", OFFm & (D.grp == "2026"), "o9"), ("2021-23 players only, 2 more seasons", OFFm & ~D.picks & (D.s <= 2023), "oL"), ("2021-23 all, 2 more seasons", OFFm & (D.s <= 2023), "oL")]:
    for cl, cv in cand.items():
        o = score(m, Y=cv["Y"], d=cv["d"], g=cv["g"], out=out); c6[f"{lab}|{cl}"] = o; print(line(f"{lab[:24]} {cl}", o))
print("\n7) summary splits, shipped vs d .9 / g 1.0 (shipped PVT)")
summ = {}
for cl, cv in [("shipped", cand["shipped"]), ("v119", cand["d.9 g1 PVT"])]:
    for g_ in ("2021-24", "2025", "2026"):
        for lab, m in [("all", OFFm), ("young", OFFm & D.young), ("not_young", OFFm & ~D.young), ("consolidation", OFFm & D.cons), ("picks", OFFm & D.picks), ("players_only", OFFm & ~D.picks), ("dynasty", OFFm & (D.ty == 2)), ("keeper", OFFm & (D.ty == 1))]:
            o = score(m & (D.grp == g_), Y=cv["Y"], d=cv["d"], g=cv["g"]); summ[f"{cl}|{g_}|{lab}"] = o
            print(f"  {cl:8s} {g_} {lab:14s} n={o['n']:5d} acc {o['won']:.1%} said {o['said']:.1%} brier {o['brier']:.4f} said60 won {o['60']['won']} said70 won {o['70']['won']} said80 won {o['80']['won']} (n80 {o['80']['n']})")
res["summary"] = summ
res["cand"] = c6; res["pvt_refit"] = dict(d=.9, g=1.0, X=list(X0), Y=list(Y9))
json.dump(res, open(B + "/e25.json", "w"), indent=1, default=float)
