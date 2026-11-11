"""B4 / e26: grade every rest-of-season estimate the app uses, plus naive benchmarks and a fitted blend.
Fit seasons 2021-24 (checkpoints 3..14); held out 2025 (wk 4/8/11) and 2026 (wk 4 next-4; wk 4/8 through the last
archived week). Population: QB/RB/WR/TE with a role known at the checkpoint: (>=2 games and PPG >= 5) or Sleeper's
projection for the week >= 5. Two outcome units: per team game (bye weeks out, missed games = 0) and per game played."""
import os, json, collections, numpy as np, pandas as pd
from sklearn.linear_model import QuantileRegressor
B = os.path.dirname(os.path.abspath(__file__))
D = pd.read_pickle(B + "/e26_panel.pkl")
pw = []
for y in range(2021, 2027):
    t = pd.read_csv(f"{B}/dl/pw_{y}.csv", low_memory=False, usecols=["player_id", "week", "season_type", "fantasy_points_ppr"])
    t = t[t.season_type == "REG"]; t["s"] = y; pw.append(t)
PW = pd.concat(pw)
ids = pd.read_csv(B + "/dl/ids.csv", low_memory=False).dropna(subset=["sleeper_id"])
g2s = dict(zip(ids.gsis_id, ids.sleeper_id.astype(int).astype(str)))
PW["pid"] = PW.player_id.map(g2s); PW = PW.dropna(subset=["pid"])
# neutral(p): career PPR games/points (archive starts 2021; the app's file starts 2018), shrunk k=8 to the position mean
def neutral_col(D):
    out = np.full(len(D), np.nan)
    for (y, w), idx in D.groupby(["s", "w"]).groups.items():
        sub = PW[(PW.s < y) | ((PW.s == y) & (PW.week < w))].groupby("pid").fantasy_points_ppr.agg(["size", "sum"])
        d = D.loc[idx]; j = d.pid.map(sub["size"]); t = d.pid.map(sub["sum"])
        m = {}
        for pos in ("QB", "RB", "WR", "TE"):
            sel = d.pos == pos; m[pos] = t[sel].sum() / max(1, j[sel].sum())
        mm = d.pos.map(m)
        v = (t + 8 * mm) / (j + 8)
        out[D.index.get_indexer(idx)] = np.where(j > 0, v, np.nan)
    return out
D["neutral"] = neutral_col(D)

def app_ros(r):
    """rosPPG as shipped (live mode, PPR): .62 PPG + .38 this week's Sleeper projection, depth/injury cuts, xFP nudge,
    roleAvail. Not replayable: the news multiplier (p.news.m)."""
    ppg = None if np.isnan(r.ppg) else r.ppg; pj = None if (r.proj is None or np.isnan(r.proj) or r.bye) else r.proj
    if ppg is not None and pj is not None: v = .62 * ppg + .38 * pj
    elif ppg is not None: v = ppg * .94
    elif pj is not None: v = pj
    else: v = 0.0
    dc = r.dc if r.dc == r.dc and r.dc is not None else None
    if dc and r.pos != "QB" and dc > 1: v *= .92 if dc == 2 else .8
    inj = str(r.inj or "")
    import re
    if re.search(r"\bout\b|\bir\b|doubt", inj, re.I): v *= .8
    # v21 xFP nudge
    if r.ag >= 1 and r.xfp == r.xfp:
        x = r.xfp * .65 + r.x3 * .35 if r.ag >= 5 else r.xfp
        if not (r.ag < 4 or not (r.fp == r.fp) or r.fp < 2 or not v > 0):
            sc = max(.6, min(1.6, (ppg or r.fp) / r.fp)); t = x * sc
            v = v * (1 + max(-.2, min(.2, (t - v) / max(4, v))) * .35)
    # roleAvail
    a = 1.0
    if r.pos == "QB" and dc and dc >= 2: a = .12 if dc == 2 else .04
    elif dc and dc >= 4 and r.pos != "QB": a = .5
    absent = re.search(r"\bout\b|\bir\b|\bpup\b|\bsus|doubt", inj, re.I)
    if (r.gp > 0 or r.ag > 0) and r.w > 2 and not absent and r.nrec >= 3:
        if r.prec == 0: a *= .25
        elif r.prec == 1: a *= .6
    return v * a

WVF = ["_b","proj","ppg_k","l3_k","x_k","x3_k","lw_k","prev","hp","snap3","dsnap","ts3","dts","cs3","dcs","out","q","dc1","dc3","t5","t15","t30","t50","t100"]
import re as _re
src = open(os.path.join(B, "..", "index.html"), encoding="utf-8").read()
WVC = json.loads("{" + _re.search(r"const WVC=\{(.*?)\};", src, _re.S).group(1).replace("QB:", '"QB":').replace("RB:", '"RB":').replace("WR:", '"WR":').replace("TE:", '"TE":') + "}")
def wv_rate(r):
    """wvRate as shipped (rate per game played over the next weeks). Sleeper trending rank not archived -> 'not trending'."""
    sc = max(.55, min(1.3, r.ppg / r.fp)) if (r.ag >= 1 and r.fp == r.fp and r.fp > 3 and r.gp >= 3 and r.ppg == r.ppg) else 1.0
    gp = r.gp; ppg = r.ppg / sc if gp else None; prev = r.prev / sc if r.prev == r.prev else None
    proj = None if (r.proj is None or r.proj != r.proj) else r.proj / sc
    hurt = bool(_re.match(r"^(out|ir|pup|nfi|sus|doubt)", str(r.inj or ""), _re.I))
    if proj is None or r.bye or (hurt and proj < .5): proj = ppg if (ppg is not None and gp >= 2) else prev if prev is not None else (proj or 0)
    pg = ppg if ppg is not None else proj; l3 = r.l3 / sc if gp else pg; lw = r.lw / sc if gp else pg; k = gp / (gp + 3)
    has = r.ag >= 1
    x = r.xfp if (has and r.xfp == r.xfp) else pg; x3 = r.x3 if (has and r.x3 == r.x3) else x
    s3 = r.snap3 / 100 if r.snap3 == r.snap3 else None; s0 = r.snap / 100 if r.snap == r.snap else None
    nz = lambda v: 0 if v is None or v != v else v
    f = dict(_b=1, proj=proj, ppg_k=k * pg, l3_k=k * l3, x_k=k * x, x3_k=k * x3, lw_k=k * lw, prev=prev or 0, hp=1 if prev is not None else 0,
             snap3=s3 or 0, dsnap=(s3 - s0) if (s3 is not None and s0 is not None) else 0, ts3=nz(r.ts3), dts=(r.ts3 - r.ts) if (r.ts3 == r.ts3 and r.ts == r.ts) else 0,
             cs3=nz(r.cs3), dcs=(r.cs3 - r.cs) if (r.cs3 == r.cs3 and r.cs == r.cs) else 0, out=0, q=1 if str(r.inj or "").lower().startswith("quest") else 0,
             dc1=1 if r.dc == 1 else 0, dc3=1 if (r.dc == r.dc and r.dc is not None and r.dc >= 3) else 0)
    c = WVC[r.pos]; v = sum(c[i] * (f.get(n, 0) or 0) for i, n in enumerate(WVF))
    v = max(0, v) * sc
    if not has: v = max(0, (.55 * proj + .45 * pg if gp else proj) * sc)
    return v

D["app"] = [app_ros(r) for r in D.itertuples()]
D["wv"] = [wv_rate(r) for r in D.itertuples()]
D["n_ppg"] = D.ppg.fillna(D.proj)
D["n_l4"] = D.l4.fillna(D.proj)
D["n_proj"] = D.proj.where(D.bye == 0).fillna(D.ppg)
D["role"] = ((D.gp >= 2) & (D.ppg >= 5)) | (D.proj.fillna(0) >= 5)
for c in ["n_ppg", "n_l4", "n_proj", "app", "wv", "neutral"]: D[c] = D[c].fillna(D.n_ppg).fillna(0)

# fitted blend (runtime inputs only)
def feats(d):
    k = d.gp / (d.gp + 3)
    pg = d.ppg.fillna(d.proj).fillna(0); pj = d.proj.where(d.bye == 0).fillna(pg).fillna(0)
    l3 = d.l3.fillna(pg); x = d.xfp.where(d.ag >= 1).fillna(pg); x3 = d.x3.where(d.ag >= 1).fillna(x)
    inj = d.inj.fillna("").astype(str)
    out = inj.str.contains("Out|Doubt", case=False).astype(float); q = inj.str.contains("Quest", case=False).astype(float)
    dc = d.dc.fillna(1)
    miss = np.where(d.nrec > 0, 1 - d.prec / d.nrec.clip(lower=1), 0)
    age = d.age.fillna(26).clip(20, 40)
    prev = d.prev.fillna(pg); hp = d.prev.notna().astype(float)
    return pd.DataFrame(dict(pj=pj, ppg_k=k * pg, l3_k=k * l3, x_k=k * x, x3_k=k * x3, prev=(1 - k) * prev, hp=hp, k=k,
        out=out, out_pj=out * pj, q=q, dc2=(dc == 2).astype(float) * pj, dc3=(dc >= 3).astype(float) * pj,
        miss=miss * pj, age=(age - 26) * pj / 10, wk=d.w * pj / 10))
FCOLS = None
def fit_blend(train, ycol, gcol):
    global FCOLS
    M = {}
    for pos in ("QB", "RB", "WR", "TE"):
        t = train[(train.pos == pos) & train.role & (train[gcol] >= 1)]
        X = feats(t); FCOLS = list(X.columns); y = t[ycol] / t[gcol]
        if len(t) > 6000: idx = np.random.RandomState(7).choice(len(t), 6000, replace=False); X, y = X.iloc[idx], y.iloc[idx]
        q = QuantileRegressor(quantile=.5, alpha=0.0, solver="highs").fit(X, y)
        M[pos] = (q.intercept_, q.coef_)
    return M
def pred_blend(M, d):
    X = feats(d); out = np.zeros(len(d))
    for pos, (b, c) in M.items():
        s = (d.pos == pos).values; out[s] = np.maximum(0, b + X.values[s] @ c)
    return out
TR = D[D.s <= 2024]
M_R = fit_blend(TR, "yR", "gR")      # rest of season, per team game
M_4 = fit_blend(TR, "y4", "g4")      # next 4, per team game
D["fitR"] = pred_blend(M_R, D); D["fit4"] = pred_blend(M_4, D)

EST = ["app", "neutral", "wv", "n_ppg", "n_l4", "n_proj", "fitR", "fit4"]
def grade(d, ycol, gcol, pcol, unit):
    if unit == "wk": d = d[d[gcol] >= 1]; y = d[ycol] / d[gcol]
    else: d = d[d[pcol] >= 1]; y = d[ycol] / d[pcol]
    return len(d), {e: round(float(np.mean(np.abs(d[e] - y))), 3) for e in EST}
R = {}
lines = []
for s in (2021, 2022, 2023, 2024, 2025, 2026):
    for w in (4, 8, 11):
        d0 = D[(D.s == s) & (D.w == w) & D.role]
        if not len(d0): continue
        for hz, ycol, gcol, pcol in (("next4", "y4", "g4", "p4"), ("ros", "yR", "gR", "pR"), ("todate", "yP", "gP", "pP")):
            if hz == "todate" and s != 2026: continue
            if d0[gcol].isna().all(): continue
            for unit in ("wk", "gp"):
                n, g = grade(d0.dropna(subset=[gcol]), ycol, gcol, pcol, unit)
                R[f"{s}|wk{w}|{hz}|{unit}"] = dict(n=n, **g)
                for pos in ("QB", "RB", "WR", "TE"):
                    n2, g2 = grade(d0[d0.pos == pos].dropna(subset=[gcol]), ycol, gcol, pcol, unit)
                    R[f"{s}|wk{w}|{hz}|{unit}|{pos}"] = dict(n=n2, **g2)
json.dump(dict(R=R, M_R={k: [float(v[0])] + [float(x) for x in v[1]] for k, v in M_R.items()},
               M_4={k: [float(v[0])] + [float(x) for x in v[1]] for k, v in M_4.items()}, F=FCOLS), open(B + "/e26_eval.json", "w"), indent=0)
D.to_pickle(B + "/e26_scored.pkl")
hdr = f"{'key':34s} {'n':>5s} " + " ".join(f"{e:>7s}" for e in EST)
print(hdr)
for k, v in R.items():
    if k.count("|") == 3: print(f"{k:34s} {v['n']:5d} " + " ".join(f"{v[e]:7.3f}" for e in EST))
