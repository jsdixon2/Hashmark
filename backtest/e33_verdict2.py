"""F1 / e33 item 1b (coordinator review): like-for-like "expected" for the verdict. Pace = PPG per game PLAYED, so the
expected value must be per game played too. Fits the e26/v114 OLS (same 16 runtime features, per position) on the
per-game-played target (rest-of-season points / games played, weight games played) on 2021-24 ("pgp"), and the v114-style
blend .25 old rosPPG + .75 pgp ("pgp_bl"). Held out 2025 (wk 4/8/11, rest of season) and 2026 (wk 4/8, through wk 9).
Compares per-game-played MAE and buy/sell calls (thr max(1.5,.15 exp)) with neutral, season PPG, v114 (hm). Also prints
the 2021-25 refit coefficients (for shipping)."""
import os, json, numpy as np, pandas as pd
from sklearn.linear_model import LinearRegression
B = os.path.dirname(os.path.abspath(__file__))
D = pd.read_pickle(B + "/e26_scored.pkl")
src = open(B + "/e26_eval.py").read(); ns = {}
exec(src.split("# fitted blend (runtime inputs only)")[1].split("FCOLS = None")[0], {"np": np, "pd": pd}, ns); feats = ns["feats"]
def fit(train):
    M = {}
    for pos in ("QB", "RB", "WR", "TE"):
        t = train[(train.pos == pos) & train.role & (train.pR >= 1)]
        m = LinearRegression().fit(feats(t), t.yR / t.pR, sample_weight=t.pR); M[pos] = (float(m.intercept_), [float(x) for x in m.coef_])
    return M
def pred(M, d):
    X = feats(d).values; o = np.zeros(len(d))
    for pos, (b, c) in M.items():
        s = (d.pos == pos).values; o[s] = np.maximum(0, b + X[s] @ np.array(c))
    return o
M = fit(D[D.s <= 2024])
E = D[D.role & (D.gp >= 3) & D.ppg.notna()].copy()
E["pgp"] = pred(M, E); E["pgp_bl"] = .25 * E.app + .75 * E.pgp
w = np.minimum(.6, E.ag / 12); x = E.xfp
E["neut"] = np.where(x.notna() & (E.ag >= 3), E.neutral * (1 - w) + x.fillna(0) * w, E.neutral)
EST = ["neut", "ppg", "hm", "pgp", "pgp_bl"]
out = {}
for s, wk in ((2025, (4, 8, 11)), (2026, (4, 8))):
    y, g = ("yP", "pP") if s == 2026 else ("yR", "pR")
    R = E[(E.s == s) & E.w.isin(wk) & (E[g] >= 1)]; t = R[y] / R[g]; o = {"n_mae": int(len(R)), "mae": {}, "calls": {}}
    for c in EST: o["mae"][c] = round(float(np.abs(R[c].fillna(R.ppg) - t).mean()), 3)
    R2 = R[R[g] >= 2]; t2 = R2[y] / R2[g]; o["n_calls"] = int(len(R2))
    for c in EST:
        if c == "ppg": continue
        e = R2[c].fillna(R2.ppg); thr = np.maximum(1.5, .15 * e); gap = R2.ppg - e; sl = gap > thr; by = -gap > thr
        sr = int((t2[sl] < R2.ppg[sl]).sum()); br = int((t2[by] > R2.ppg[by]).sum())
        o["calls"][c] = {"sell_n": int(sl.sum()), "sell_prec": round(sr / max(1, sl.sum()), 3), "buy_n": int(by.sum()),
                         "buy_prec": round(br / max(1, by.sum()), 3), "net_right": int(2 * sr - sl.sum() + 2 * br - by.sum())}
    out[s] = o; print(s, json.dumps(o))
M2 = fit(D[D.s <= 2025]); out["coef_2021_25"] = M2
print("refit 2021-25:", json.dumps({k: [round(v[0], 4)] + [round(z, 4) for z in v[1]] for k, v in M2.items()}))
json.dump(out, open(B + "/e33_verdict2.json", "w"), indent=1)
