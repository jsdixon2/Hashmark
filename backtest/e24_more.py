"""Task B2 step 3: extra checks. (a) fits on 2021-25 tested on 2026 only; (b) blends of the shipped formula with Sleeper;
(c) week-block bootstrap of the MAE gap shipped vs Sleeper and best candidate vs shipped (2026, 2025)."""
import os, numpy as np, runpy
B = os.path.dirname(os.path.abspath(__file__))
import sys, io; _o = sys.stdout; sys.stdout = io.StringIO(); ns = runpy.run_path(f"{B}/e24_fit.py"); sys.stdout = _o
df, qfit, qpred, mae, wb, bcols, T = ns["df"], ns["qfit"], ns["qpred"], ns["mae"], ns["wb"], ns["bcols"], ns["T"]
tr = df[df.season <= 2025]; d = df[df.season == 2026]
print("2026 n", len(d), "sleeper", round(mae(d.actual, d.base), 3), "shipped", round(mae(d.actual, d.h0), 3))
for label, cols, a in [("refit10", bcols, 0), ("h0+tot", ["h0u", "t_tot"], 0), ("h0+rush+epad+sp+wind", ["h0u", "t_rush", "t_epad", "t_sp", "t_wind"], 0),
                       ("refit10+all L1 .01", bcols + ["t_" + k for k in T], .01), ("refit10+all", bcols + ["t_" + k for k in T], 0)]:
    m = qfit(tr, cols, a); p = qpred(m, d, cols); print("fit21-25", label, round(mae(d.actual, p), 3), "wk vs shipped", wb(d, p, d.h0), "vs sleeper", wb(d, p, d.base))
for y in (2025, 2026):
    e = df[df.season == y]
    print(y, "blend w*shipped+(1-w)*sleeper:", {w: round(mae(e.actual, w * e.h0 + (1 - w) * e.base), 3) for w in (0, .25, .5, .75, 1)})
rng = np.random.default_rng(0)
for y in (2025, 2026):
    e = df[df.season == y].copy(); e["g"] = np.abs(e.actual - e.base) - np.abs(e.actual - e.h0)
    wk = sorted(e.week.unique()); gs = [e[e.week == w].g.values for w in wk]
    bs = [np.mean(np.concatenate([gs[i] for i in rng.integers(0, len(gs), len(gs))])) for _ in range(2000)]
    print(y, "shipped gain over Sleeper", round(e.g.mean(), 3), "95% CI", np.round(np.percentile(bs, [2.5, 97.5]), 3))
