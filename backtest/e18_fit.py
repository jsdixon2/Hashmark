"""e18 (task B8): measure the shipped risk score and breakout odds, fit replacements, test on later seasons.

Run backtest/e18_data.py first. Prints all tables; writes .build/agents/b8/e18_fit.json (held-out numbers + coefficients).

Definitions
  Breakout (next season): among players NOT already a top finisher (this season so far or last season), finishes
    top-12 QB/TE or top-24 RB/WR in PPR points per game next season (min 8 games).
  Breakout (rest of season): same, over the weeks after the cut (min 4 games).
  Risk outcome ("bust rate"): share of his team's remaining games this season (min 4) in which he was out or scored
    under half his season-to-date points per game.  Population: 3+ games and 5.3+ ppg (the app's ros>=5 pool).
Train: feature seasons 2017-2021.  Test (never seen by the fit): 2022-2024 next-season, 2022-2026 rest-of-season/risk.
"""
import json, math, pickle, collections
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import roc_auc_score
from scipy.stats import spearmanr

R = "/home/user/Hashmark"
D = pd.DataFrame(pickle.load(open(R + "/.build/agents/b8/e18_panel.pkl", "rb")))
D = D[D.y >= 2017].copy()
D["sid"] = D["sid"].where(D["sid"].notna() & (D["sid"] != "NA"))
POS = ["QB", "RB", "WR", "TE"]
CLIFF = {"QB": 34, "RB": 27, "WR": 28, "TE": 29}  # AGE_CLIFF after v49
REPL = {"QB": 11.5, "RB": 10.5, "WR": 11, "TE": 9}  # repl() superflex
TRAIN = lambda d: d[(d.y >= 2017) & (d.y <= 2021)]
TEST = lambda d: d[d.y >= 2022]
OUT = {}


# ------------------------------------------------------------------ shipped breakout odds (computeAll + v9 + v21)
def shipped_brk(r, draft_bonus):
    a = int(math.floor(r.age)) if r.age == r.age and r.age is not None else 26
    b = {21: .42, 22: .42, 23: .34, 24: .26, 25: .16, 26: .08}.get(a, .42 if a < 21 else .03)
    if draft_bonus and r.dr == r.dr and r.dr is not None:
        b += .08 if r.dr == 1 else .04 if r.dr == 2 else 0
    ppg = r.fp if r.g else None
    if r.sproj == r.sproj and r.sproj is not None and ppg is not None and r.sproj > ppg * 1.05:
        b += .05
    if ppg is not None and r.last1 is not None and r.last1 > ppg * 1.15:
        b += .04
    b = min(.75, max(.02, b))
    if a <= 26 and r.g:  # v21 usage multiplier (sep / yacoe / ryoe not in the archive)
        k = 1
        if r.xfp == r.xfp and r.xfp is not None and r.g >= 3:
            k += max(-.3, min(.3, (r.xfp - r.fp) / max(5, r.xfp))) * .6
        if r.ts3 == r.ts3 and r.ts == r.ts and r.ts3 is not None and r.ts is not None:
            k += max(-.15, min(.15, (r.ts3 - r.ts) * 2))
        if r.snap3 == r.snap3 and r.snap == r.snap and r.snap3 is not None and r.snap is not None and r.snap3 - r.snap >= 12:
            k += .08
        b = max(0, min(.75, b * k))
    return b


# ------------------------------------------------------------------ new breakout model: features from runtime fields
THR = {}  # ppg of the Nth finisher by position (train seasons, median)


def feats(d):
    X = pd.DataFrame(index=d.index)
    T = d.pos.map(THR)
    age = d.age.fillna(26).clip(20, 38)
    for p in ("RB", "WR", "TE"):
        X["is" + p] = (d.pos == p).astype(float)
    X["young"] = (25 - age).clip(lower=0)
    X["old"] = (age - 27).clip(lower=0)
    X["rookie"] = (d.dy == d.y).astype(float)
    X["r1"] = (d.dr == 1).astype(float)
    X["r2"] = (d.dr == 2).astype(float)
    X["r3"] = (d.dr == 3).astype(float)
    X["r47"] = d.dr.between(4, 7).astype(float)
    has = d.g > 0
    fp = d.fp.where(has, 0).fillna(0)
    xfp = d.xfp.where(d.xfp.notna(), d.fp).where(has, 0).fillna(0)
    X["fp"] = fp / T
    X["xfp"] = xfp / T
    X["fp3"] = d.fp3.where(has, 0).fillna(0) / T
    X["gsh"] = (d.g / d.tg.clip(lower=1)).clip(0, 1).where(has, 0)
    X["snap"] = d.snap.fillna(0).where(has, 0) / 100
    X["pfp"] = d.pfp.where(d.pg >= 4, 0).fillna(0) / T
    X["pg"] = (d.pg.fillna(0) / 17).clip(0, 1)
    X["xfpQB"] = X.xfp * (d.pos == "QB")
    X["xfpTE"] = X.xfp * (d.pos == "TE")
    return X


def calib(p, y, bins=(0, .05, .1, .2, .3, .5, 1.01)):
    t = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = (p >= lo) & (p < hi)
        if m.sum():
            t.append([f"{int(lo*100)}-{int(min(hi,1)*100)}%", int(m.sum()), round(float(p[m].mean()), 3), round(float(y[m].mean()), 3)])
    return t


def brier(p, y): return float(np.mean((p - y) ** 2))
def logloss(p, y):
    p = np.clip(p, 1e-4, 1 - 1e-4); return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def report_brk(name, d, ycol, cols):
    y = d[ycol].values.astype(float)
    res = {"n": int(len(d)), "base": round(float(y.mean()), 4)}
    for c in cols:
        p = d[c].values
        r = {"auc": round(roc_auc_score(y, p), 3), "brier": round(brier(p, y), 4), "logloss": round(logloss(p, y), 4),
             "mean_said": round(float(p.mean()), 3), "calib": calib(p, y)}
        hi = p >= .3
        r["call30_n"] = int(hi.sum()); r["call30_hit"] = round(float(y[hi].mean()), 3) if hi.sum() else None
        top = np.argsort(-p, kind="stable")[: max(1, len(p) // 20)]
        r["top5pct_hit"] = round(float(y[top].mean()), 3)
        res[c] = r
    print(f"\n== {name}: n={res['n']} base rate {res['base']}")
    for c in cols:
        r = res[c]
        print(f"  {c:10s} AUC {r['auc']}  Brier {r['brier']}  logloss {r['logloss']}  avg said {r['mean_said']}  "
              f"calls>=30%: {r['call30_n']} hit {r['call30_hit']}  top5% hit {r['top5pct_hit']}")
        for row in r["calib"]:
            print(f"      said {row[0]:>8s}  n={row[1]:5d}  avg said {row[2]:.3f}  happened {row[3]:.3f}")
    return res


def fit_brk(ycol, label):
    d = D[~D.top_now & ~D.top_prev & D[ycol].notna()].copy()
    tr, te = TRAIN(d), TEST(d)
    X = feats(tr)
    m = LogisticRegression(C=1.0, max_iter=3000)
    mu, sd = X.mean(), X.std().replace(0, 1)
    m.fit((X - mu) / sd, tr[ycol].values)
    te = te.copy()
    te["new"] = m.predict_proba((feats(te) - mu) / sd)[:, 1]
    te["ship_live"] = [shipped_brk(r, False) for r in te.itertuples()]
    te["ship_demo"] = [shipped_brk(r, True) for r in te.itertuples()]
    cols = ["ship_live", "ship_demo", "new"]
    out = {"all": report_brk(f"{label} held-out {sorted(te.y.unique())} all eligible", te, ycol, cols)}
    rel = te[(te.fp.fillna(0) >= 5) | ((te.g == 0) & (te.dr.fillna(9) <= 2))]
    out["relevant"] = report_brk(f"{label} held-out, relevant (ppg>=5 or unplayed R1-2)", rel, ycol, cols)
    # 2022+ seasons with Sleeper projections only (shipped formula fully reconstructable)
    sp = te[te.sproj.notna()]
    out["with_sleeper_proj"] = report_brk(f"{label} held-out, players with a Sleeper projection", sp, ycol, cols)
    # refit on all seasons for shipping
    al = pd.concat([tr, TEST(d)])
    Xa = feats(al); mua, sda = Xa.mean(), Xa.std().replace(0, 1)
    ma = LogisticRegression(C=1.0, max_iter=3000).fit((Xa - mua) / sda, al[ycol].values)
    w = ma.coef_[0] / sda.values
    b0 = float(ma.intercept_[0] - (ma.coef_[0] * mua.values / sda.values).sum())
    wt = m.coef_[0] / sd.values
    print("  coefficients (raw units) train-only / all seasons:")
    for k, a, c in zip(X.columns, wt, w):
        print(f"    {k:8s} {a:+.3f}  {c:+.3f}")
    out["coef"] = {"b0": round(b0, 4), **{k: round(float(v), 4) for k, v in zip(X.columns, w)}}
    out["coef_train"] = {"b0": round(float(m.intercept_[0] - (m.coef_[0] * mu.values / sd.values).sum()), 4), **{k: round(float(v), 4) for k, v in zip(X.columns, wt)}}
    return out


# ------------------------------------------------------------------ shipped risk (riskEngine v11 + v77)
RK_W = {"vol": .22, "floor": .17, "health": .2, "role": .16, "age": .1, "td": .09, "trend": .06}
RK_WD = dict(RK_W, age=.18, trend=.04)


def raw_risk(r, tgmax):
    pos, a = r.pos, (r.age if r.age == r.age else 26)
    a = int(math.floor(a))
    lg = list(r.pts_w); n = len(lg); m = sum(lg) / n if n else None
    prior = {"QB": .38, "RB": .5, "WR": .55, "TE": .6}[pos]; cv = prior
    if n >= 3 and m > 0:
        sdv = math.sqrt(sum((x - m) ** 2 for x in lg) / n); cv = (sdv / max(2, m) * n + prior * 3) / (n + 3)
    o = {"vol": cv}
    R_ = REPL[pos]; dud = sum(1 for x in lg if x < .6 * R_) / n if n else .3
    o["floor"] = (dud * n + .3 * 2) / (n + 2)
    h = {"QB": .08, "RB": .2, "WR": .13, "TE": .14}[pos] + ((a - 26) * .04 if pos == "RB" and a >= 27 else 0)
    st = r.inj_next
    if st == "Out": h += .75
    elif st == "Doubtful": h += .5
    elif st == "Questionable": h += .3
    miss = r.miss or 0
    if miss > 0:
        tg = max(1, tgmax or n or 1); h += min(.45, miss / max(tg, miss) * .9)
    o["health"] = h
    sn = [x for x in r.snap_w if x is not None][-3:]
    snap = sum(sn) / len(sn) if sn else None
    ro = .1 if pos == "QB" else .3
    if snap is not None:
        ro = (.6 if snap < 85 else .08) if pos == "QB" else max(0, (80 - snap) / 80)
    o["role"] = max(0, ro)
    cl = CLIFF[pos]; o["age"] = 1 + (a - cl) * .35 if a >= cl else (a - (cl - 2)) / 2 * .8 if a >= cl - 2 else 0
    tdp = None
    if n >= 3 and m > 0:
        tdp = min(1, sum(r.td_w) / (m * n))
    o["td"] = .3 if tdp is None else max(0, tdp - (.3 if pos == "QB" else .2))
    tr = 0
    if n >= 5:
        l3, e = lg[-3:], lg[:-3]; pl, pe = sum(l3) / 3, sum(e) / len(e); tr = (pe - pl) / max(4, pe)
        s3 = [x for x in r.snap_w[-3:] if x is not None]; se = [x for x in r.snap_w[:-3] if x is not None]
        if s3 and se: tr += (sum(se) / len(se) - sum(s3) / len(s3)) / 100
    o["trend"] = tr
    return o, st == "Out"


def pctl(arr, v):
    lo = np.searchsorted(arr, v, "left"); hi = np.searchsorted(arr, v, "right")
    return round(100 * (lo + (hi - lo) / 2) / len(arr)) if len(arr) else 50


def shipped_risk(g, W):
    """g: one (y, cut, pos) group = the pool; returns risk per row"""
    tgmax = {}
    for r in g.itertuples():
        tgmax[r.team] = max(tgmax.get(r.team, 0), r.g)
    raws = [raw_risk(r, tgmax.get(r.team)) for r in g.itertuples()]
    dist = {k: np.sort([o[k] for o, _ in raws]) for k in W}
    ws = sum(W.values()); comp = []
    for o, out in raws:
        c = {k: pctl(dist[k], o[k]) for k in W}
        if out: c["health"] = max(c["health"], 95)
        if o["age"] == 0: c["age"] = min(c["age"], 20)
        comp.append(sum(c[k] * W[k] for k in W) / ws)
    cd = np.sort(comp)
    return [min(98, max(2, pctl(cd, x))) for x in comp]


def risk_feats(d):
    X = pd.DataFrame(index=d.index)
    for p in ("RB", "WR", "TE"):
        X["is" + p] = (d.pos == p).astype(float)
    cv, dud, td, tr, snap3 = [], [], [], [], []
    for r in d.itertuples():
        lg = list(r.pts_w); n = len(lg); m = sum(lg) / n
        prior = {"QB": .38, "RB": .5, "WR": .55, "TE": .6}[r.pos]
        sdv = math.sqrt(sum((x - m) ** 2 for x in lg) / n)
        cv.append((sdv / max(2, m) * n + prior * 3) / (n + 3))
        dud.append(sum(1 for x in lg if x < .5 * m) / n)
        td.append(min(1, sum(r.td_w) / max(1e-9, m * n)))
        tr.append((sum(lg[-3:]) / 3 - m) / max(4, m) if n >= 5 else 0)
        sn = [x for x in r.snap_w if x is not None][-3:]
        snap3.append(sum(sn) / len(sn) / 100 if sn else np.nan)
    X["cv"] = cv; X["dud"] = dud; X["td"] = td; X["trend"] = tr
    X["snap3"] = pd.Series(snap3, index=d.index).fillna(.6)
    X["lowsnap"] = (X.snap3 < .5).astype(float)
    X["gsh"] = (d.g / d.tg.clip(lower=1)).clip(0, 1)
    X["missr"] = (d.miss.fillna(0) / d.tg.clip(lower=1)).clip(0, 1)
    X["out"] = (d.inj_next == "Out").astype(float)
    X["doubt"] = (d.inj_next == "Doubtful").astype(float)
    X["quest"] = (d.inj_next == "Questionable").astype(float)
    age = d.age.fillna(26)
    X["pastcliff"] = (age - d.pos.map(CLIFF) + 2).clip(lower=0)
    T = d.pos.map(THR)
    X["fp"] = d.fp / T
    X["xfpgap"] = ((d.xfp.fillna(d.fp) - d.fp) / T)
    return X


def within_spear(d, c, y):
    rs = []
    for _, g in d.groupby(["y", "cut", "pos"]):
        if len(g) >= 8:
            rs.append(spearmanr(g[c], g[y]).correlation)
    return round(float(np.nanmean(rs)), 3)


TB = [20, 36, 52, 67, 82, 101]
TN = ["Bubble-wrapped", "Sunday nap", "Coin flip", "Spicy nugget", "Hold my beer", "Full-send fireworks"]


def tiers(d, c, y):
    t = np.searchsorted(TB, d[c].values, "right")
    out = []
    for i, nm in enumerate(TN):
        m = t == i
        if m.sum(): out.append([nm, int(m.sum()), round(float(d[y].values[m].mean()), 3)])
    return out


def main():
    # thresholds: ppg of the Nth finisher (median over train seasons) - computed from next_ppg ranks
    full = D[D.cut == D["last"]]
    for pos, N in (("QB", 12), ("RB", 24), ("WR", 24), ("TE", 12)):
        v = []
        for y in range(2017, 2022):
            g = full[(full.y == y) & (full.pos == pos) & (full.g >= 8)].fp.sort_values(ascending=False)
            if len(g) >= N: v.append(float(g.iloc[N - 1]))
        THR[pos] = round(float(np.median(v)), 1)
    print("thresholds (ppg of the last top finisher):", THR)
    OUT["thr"] = THR

    OUT["brk_next"] = fit_brk("brk_next", "BREAKOUT NEXT SEASON")
    OUT["brk_ros"] = fit_brk("brk_ros", "BREAKOUT REST OF SEASON")

    # ---------------- risk
    pool = D[(D.g >= 3) & (D.fp >= 5.32) & D.bust_ros.notna() & (D.cut < D["last"])].copy()
    sr, srd = pd.Series(index=pool.index, dtype=float), pd.Series(index=pool.index, dtype=float)
    for _, g in pool.groupby(["y", "cut", "pos"]):
        sr[g.index] = shipped_risk(g, RK_W); srd[g.index] = shipped_risk(g, RK_WD)
    pool["ship"], pool["ship_dyn"] = sr, srd
    tr, te = TRAIN(pool), TEST(pool).copy()
    X = risk_feats(tr); mu, sd = X.mean(), X.std().replace(0, 1)
    m = Ridge(alpha=1.0).fit((X - mu) / sd, tr.bust_ros.values)
    te["pred"] = m.predict((risk_feats(te) - mu) / sd)
    newr = pd.Series(index=te.index, dtype=float)
    for _, g in te.groupby(["y", "cut", "pos"]):
        a = np.sort(g.pred.values); newr[g.index] = [min(98, max(2, pctl(a, x))) for x in g.pred.values]
    te["new"] = newr
    res = {"n": int(len(te)), "seasons": sorted(int(x) for x in te.y.unique()), "base": round(float(te.bust_ros.mean()), 3)}
    print(f"\n== RISK held-out n={res['n']} seasons {res['seasons']} (rest-of-season bust rate, mean {res['base']})")
    for c in ("ship", "ship_dyn", "new"):
        s = within_spear(te, c, "bust_ros"); sm = within_spear(te, c, "miss_ros")
        t = tiers(te, c, "bust_ros"); top = te[te[c] >= 82].bust_ros.mean(); low = te[te[c] < 36].bust_ros.mean()
        res[c] = {"spearman_bust": s, "spearman_missed": sm, "tiers": t, "top_tier_bust": round(float(top), 3), "safe_bust": round(float(low), 3)}
        print(f"  {c:9s} within-pos Spearman vs bust rate {s}  vs games missed {sm}  top tier (82+) bust {top:.3f}  safe (<36) {low:.3f}")
        for row in t: print(f"      {row[0]:20s} n={row[1]:5d} bust {row[2]:.3f}")
    # secondary: season-to-season drop, end-of-season rows of the same pool definition
    print("  per held-out season Spearman ship / new:", {int(y): (within_spear(g, "ship", "bust_ros"), within_spear(g, "new", "bust_ros")) for y, g in te.groupby("y")})
    res["per_season"] = {int(y): [within_spear(g, "ship", "bust_ros"), within_spear(g, "new", "bust_ros")] for y, g in te.groupby("y")}
    Xa_all = pd.concat([tr, TEST(pool)]); Xa = risk_feats(Xa_all); mua, sda = Xa.mean(), Xa.std().replace(0, 1)
    ma = Ridge(alpha=1.0).fit((Xa - mua) / sda, Xa_all.bust_ros.values)
    w = ma.coef_ / sda.values; b0 = float(ma.intercept_ - (ma.coef_ * mua.values / sda.values).sum())
    print("  risk coefficients (raw units, all seasons):", {k: round(float(v), 4) for k, v in zip(X.columns, w)}, "b0", round(b0, 4))
    res["coef"] = {"b0": round(b0, 4), **{k: round(float(v), 4) for k, v in zip(X.columns, w)}}
    OUT["risk"] = res
    json.dump(OUT, open(R + "/.build/agents/b8/e18_fit.json", "w"), indent=1, default=float)


if __name__ == "__main__":
    main()
