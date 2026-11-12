"""F1 / e33 item 1: the verdict card's "expected" (buy/sell "pace vs expected").
Candidates on the e26 panel (runtime inputs only): neutral(p) as shipped (career PPR PPG shrunk k=8 to the position
mean, + xFP blend w=min(.6,g/12)), plain season PPG, and the v114 rest-of-season estimate (hm = 25% old rosPPG + 75%
OLS fitted on 2021-24, never saw 2025/26). Held out: 2025 (wk 4/8/11, rest of season) and 2026 (wk 4/8, through the
last archived week). Units: per team game (app's ROS unit) and per game played (the unit of "pace").
Also grades the buy/sell call: sell = pace - exp > max(1.5, .15 exp); right when his later per-game-played average
falls below his pace; buy = exp - pace > thr, right when it rises above pace."""
import os, json, numpy as np, pandas as pd
B = os.path.dirname(os.path.abspath(__file__))
D = pd.read_pickle(B + "/e26_scored.pkl")
D = D[D.role & (D.gp >= 3) & D.ppg.notna()].copy()
w = np.minimum(.6, D.ag / 12); x = D.xfp
D["neut"] = np.where(x.notna() & (D.ag >= 3), D.neutral * (1 - w) + x.fillna(0) * w, D.neutral)
D["season_ppg"] = D.ppg
out = {}
def grade(tag, R, y, g):
    R = R[R[g] >= 1]; t = R[y] / R[g]; o = {"n": int(len(R))}
    for c in ("neut", "season_ppg", "hm"):
        e = R[c].fillna(R.ppg)
        o[c] = round(float(np.abs(e - t).mean()), 3)
    return o
def calls(tag, R, y="yR", g="pR"):
    R = R[R[g] >= 2]; t = R[y] / R[g]; o = {}
    for c in ("neut", "hm", "season_ppg"):
        e = R[c].fillna(R.ppg); thr = np.maximum(1.5, .15 * e); gap = R.ppg - e
        s = gap > thr; b = -gap > thr
        o[c] = {"sell_n": int(s.sum()), "sell_right": round(float((t[s] < R.ppg[s]).mean()), 3) if s.any() else None,
                "sell_drop": round(float((R.ppg[s] - t[s]).mean()), 2) if s.any() else None,
                "buy_n": int(b.sum()), "buy_right": round(float((t[b] > R.ppg[b]).mean()), 3) if b.any() else None,
                "buy_rise": round(float((t[b] - R.ppg[b]).mean()), 2) if b.any() else None, "of": int(len(R))}
    return o
for s, wk in ((2021, (4, 8, 11)), (2022, (4, 8, 11)), (2023, (4, 8, 11)), (2024, (4, 8, 11)), (2025, (4, 8, 11)), (2026, (4, 8))):
    R = D[(D.s == s) & D.w.isin(wk)]
    y, g, gp = ("yP", "gP", "pP") if s == 2026 else ("yR", "gR", "pR")
    out[s] = {"per_team_game": grade(s, R, y, g), "per_game_played": grade(s, R, y, gp), "calls": calls(s, R, y, gp)}
    print(s, json.dumps(out[s]))
json.dump(out, open(B + "/e33_verdict.json", "w"), indent=1)
