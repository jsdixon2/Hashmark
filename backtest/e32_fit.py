"""e32 fit/grade: replay the app's season simulation at checkpoints after weeks 4/8/11 (backtest/e32_recs.pkl), grade
playoff and title odds (Brier, log loss, calibration), baselines (standings rank, points-for rank: empirical rates by
rank fitted on the train seasons), and grid-search PO.u / PO.sh / season-to-date blend a / median simulation on 2022-23,
checked on 2024-25. Output backtest/e32.json."""
import pickle, json, os, sys, itertools, collections
import numpy as np
B = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, B)
from e32_sim import sim
RA = pickle.load(open(B + "/e32_recs.pkl", "rb")); R = [r for r in RA if not r.get("last")]; RL = [r for r in RA if r.get("last")]
TR = lambda r: r["s"] <= 2023
N = int(os.environ.get("E32_N", 1500))

def run(recs, **kw):
    out = []
    for i, r in enumerate(recs):
        po, ch = sim(r, N=N, seed=1000 + i, **kw)
        out.append((r, po, ch))
    return out

def grade(out, key):
    rows = collections.defaultdict(lambda: [[], []])
    for r, po, ch in out:
        p = po if key == "po" else ch; y = r[key]
        rows[r["c"]][0].extend(p); rows[r["c"]][1].extend(y); rows["all"][0].extend(p); rows["all"][1].extend(y)
    res = {}
    for c, (p, y) in rows.items():
        p = np.clip(np.array(p), 1e-3, 1 - 1e-3); y = np.array(y)
        res[str(c)] = dict(n=int(len(y)), brier=round(float(np.mean((p - y) ** 2)), 4),
                           ll=round(float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))), 4),
                           base=round(float(np.mean(y)), 3))
    return res

def calib(out, key, bins=(0, .02, .1, .25, .4, .6, .75, .9, .98, 1.0001)):
    res = {}
    for c in (4, 8, 11, "all"):
        p = []; y = []
        for r, po, ch in out:
            if c != "all" and r["c"] != c: continue
            p.extend(po if key == "po" else ch); y.extend(r[key])
        p = np.array(p); y = np.array(y); rows = []
        for lo, hi in zip(bins[:-1], bins[1:]):
            m = (p >= lo) & (p < hi)
            if m.sum(): rows.append([f"{lo:.0%}-{min(hi,1):.0%}", int(m.sum()), round(float(p[m].mean()), 3), round(float(y[m].mean()), 3)])
        res[str(c)] = rows
    return res

def ranks(r):
    n = r["n"]; ordS = sorted(range(n), key=lambda i: (-r["w"][i], -r["pf"][i], i)); ordP = sorted(range(n), key=lambda i: (-r["pf"][i], i))
    rs = np.empty(n, int); rp = np.empty(n, int)
    for k, i in enumerate(ordS): rs[i] = k
    for k, i in enumerate(ordP): rp[i] = k
    return rs, rp

def baseline(train, test, which):
    tab = collections.defaultdict(lambda: np.zeros(2)); tabc = collections.defaultdict(lambda: np.zeros(2))
    def kk(r, rk, key): return (r["c"], int(np.clip(rk - r["pt"], -6, 6))) if key == "po" else (r["c"], int(min(rk, 9)), r["pt"] <= 4)
    for r in train:
        rk = ranks(r)[which]
        for i in range(r["n"]):
            for key, T in (("po", tab), ("ch", tabc)):
                T[kk(r, rk[i], key)] += (r[key][i], 1)
    out = []
    for r in test:
        rk = ranks(r)[which]; po = np.zeros(r["n"]); ch = np.zeros(r["n"])
        for i in range(r["n"]):
            a = tab[kk(r, rk[i], "po")]; b = tabc[kk(r, rk[i], "ch")]
            po[i] = (a[0] + .5) / (a[1] + 1); ch[i] = (b[0] + 1 / r["n"]) / (b[1] + 1)
        ch = ch / ch.sum()
        out.append((r, po, ch))
    return out

def score(out):  # fit objective: Brier playoffs + Brier title (all checkpoints)
    return grade(out, "po")["all"]["brier"] + grade(out, "ch")["all"]["brier"]

if __name__ == "__main__":
    train = [r for r in R if TR(r)]; test = [r for r in R if not TR(r)]
    print("train", len(train), "records", len({r['lid'] for r in train}), "leagues", sum(r['n'] for r in train), "team-checkpoints;",
          "test", len(test), len({r['lid'] for r in test}), sum(r['n'] for r in test), flush=True)
    res = {"n": {"train_leagues": len({r['lid'] for r in train}), "test_leagues": len({r['lid'] for r in test}),
                 "train_team_cps": sum(r['n'] for r in train), "test_team_cps": sum(r['n'] for r in test)}}
    APP = dict(u=.04, sh=.5)
    grid = []
    for u in (0, .04, .08, .12, .16):
        for sh in (0, .15, .3, .5):
            for a in (0, .25, .5):
                o = run(train, u=u, sh=sh, a=a); sc = score(o)
                grid.append((sc, u, sh, a, grade(o, "po")["all"]["brier"], grade(o, "ch")["all"]["brier"]))
                print(f"u={u} sh={sh} a={a}: {sc:.4f} po {grid[-1][4]} ch {grid[-1][5]}", flush=True)
    grid.sort(); res["grid"] = grid
    _, u, sh, a, _, _ = grid[0]
    km = []
    for kmul in (.8, .9, 1.0, 1.1, 1.2):
        o = run(train, u=u, sh=sh, a=a, kmul=kmul); km.append((score(o), kmul)); print("kmul", kmul, km[-1][0], flush=True)
    km.sort(); kmul = km[0][1]; res["kmul"] = km
    om = run(train, u=u, sh=sh, a=a, kmul=kmul, med=True); medgain = score(om) < score(run(train, u=u, sh=sh, a=a, kmul=kmul))
    BEST = dict(u=u, sh=sh, a=a, kmul=kmul, med=medgain); print("best", BEST, flush=True)
    res["best"] = BEST
    for name, tr, te in (("train", train, train), ("test", train, test)):
        o_app = run(te, **APP); o_new = run(te, **BEST); o_rk = baseline(tr, te, 0); o_pf = baseline(tr, te, 1)
        res[name] = {}
        for lab, o in (("app", o_app), ("fitted", o_new), ("standings_rank", o_rk), ("pf_rank", o_pf)):
            res[name][lab] = {"po": grade(o, "po"), "ch": grade(o, "ch"), "cal_po": calib(o, "po"), "cal_ch": calib(o, "ch")}
        if name == "test":
            for s in (2024, 2025):
                o1 = [x for x in o_app if x[0]["s"] == s]; o2 = [x for x in o_new if x[0]["s"] == s]
                res[name][f"by_season_{s}"] = {"app": [grade(o1, "po")["all"]["brier"], grade(o1, "ch")["all"]["brier"]],
                                               "fitted": [grade(o2, "po")["all"]["brier"], grade(o2, "ch")["all"]["brier"]]}
    json.dump(res, open(B + "/e32.json", "w"), indent=1)
    t = res["test"]
    for lab in t:
        if lab.startswith("by_"): print(lab, t[lab]); continue
        print(lab, "po", {c: (v["brier"], v["ll"]) for c, v in t[lab]["po"].items()}, "ch", {c: v["brier"] for c, v in t[lab]["ch"].items()})
