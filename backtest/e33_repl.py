"""F1 / e33 item 2: replacement levels. At weeks 4/8/11 of 2021-25 (e26 panel), the level of the k-th best player at each
position (mean of ranks k..k+4, 12-team league: QB 13 in 1QB / 25 in Superflex, RB 30, WR 37, TE 13), on four scales:
season PPG (games played >= 2), the old rosPPG ("app"), the v114 estimate ("hm", now shown as ROS/wk), and the real
rest-of-season points per team game ("real"). Shipped constants: QB 16 (1QB) / 11.5 (SF), RB 10.5, WR 11, TE 9."""
import os, json, numpy as np, pandas as pd
B = os.path.dirname(os.path.abspath(__file__))
D = pd.read_pickle(B + "/e26_scored.pkl")
D = D[D.s.between(2021, 2025) & D.w.isin([4, 8, 11]) & (D.gR >= 1)].copy()
D["real"] = D.yR / D.gR
D["sppg"] = np.where(D.gp >= 2, D.ppg, np.nan)
K = {"QB1": ("QB", 13), "QBSF": ("QB", 25), "RB": ("RB", 30), "WR": ("WR", 37), "TE": ("TE", 13)}
SH = {"QB1": 16, "QBSF": 11.5, "RB": 10.5, "WR": 11, "TE": 9}
out = {}
for key, (pos, k) in K.items():
    row = {"shipped": SH[key]}
    for c in ("sppg", "app", "hm", "real"):
        v = []
        for (s, w), g in D[D.pos == pos].groupby(["s", "w"]):
            x = np.sort(g[c].dropna().values)[::-1]
            if len(x) >= k + 4: v.append(x[k - 1:k + 4].mean())
        row[c] = round(float(np.mean(v)), 2)
    # by season for hm
    row["hm_by_season"] = {}
    for s in range(2021, 2026):
        v = []
        for w, g in D[(D.pos == pos) & (D.s == s)].groupby("w"):
            x = np.sort(g.hm.dropna().values)[::-1]; v.append(x[k - 1:k + 4].mean())
        row["hm_by_season"][s] = round(float(np.mean(v)), 2)
    out[key] = row; print(key, row)
json.dump(out, open(B + "/e33_repl.json", "w"), indent=1)
