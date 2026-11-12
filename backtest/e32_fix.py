"""e32 fix test. The app's live league loads wins through last week and future matchups from week+1, so during a week
the CURRENT week's game is never simulated (one game short all week); median leagues' future median wins are not
simulated either. Variants graded at checkpoints 4/8/11 (live during week c+1 = record through c, games c+2..):
  shipped   : no current-week game, no median           (what the app shows during the week)
  shipped_tue: all remaining games, no median           (what the app shows between weeks; graded in e32_fit 'app')
  fixed     : all remaining games + median simulated     (v116)
then a PO.u / PO.sh refit on top of 'fixed' (2022-23), checked on 2024-25. Output backtest/e32_fix.json."""
import os, sys, json, copy
import numpy as np
B = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, B)
import e32_fit as F
R = F.R
def drop_cur(recs):
    out = []
    for r in recs:
        r2 = dict(r); r2["fut"] = r["fut"][1:]; out.append(r2)
    return out
train = [r for r in R if F.TR(r)]; test = [r for r in R if not F.TR(r)]
res = {}
def summ(o):
    return {"po": F.grade(o, "po"), "ch": F.grade(o, "ch"), "cal_po": F.calib(o, "po"), "cal_ch": F.calib(o, "ch")}
grid = []
for u in (0, .04, .08, .12):
    for sh in (.15, .3, .5, .65):
        o = F.run(train, u=u, sh=sh, med=True); grid.append((F.score(o), u, sh)); print("fixed u", u, "sh", sh, round(grid[-1][0], 4), flush=True)
grid.sort(); res["grid_fixed"] = grid; _, bu, bsh = grid[0]
for name, recs in (("train", train), ("test", test)):
    res[name] = {"shipped": summ(F.run(drop_cur(recs), u=.04, sh=.5)), "shipped_tue": summ(F.run(recs, u=.04, sh=.5)),
                 "fixed": summ(F.run(recs, u=.04, sh=.5, med=True)), "fixed_refit": summ(F.run(recs, u=bu, sh=bsh, med=True))}
    for s in sorted({r["s"] for r in recs}):
        rr = [r for r in recs if r["s"] == s]
        a = F.run(drop_cur(rr), u=.04, sh=.5); b = F.run(rr, u=.04, sh=.5, med=True)
        res[name][f"season_{s}"] = {"shipped": [F.grade(a, "po")["all"]["brier"], F.grade(a, "ch")["all"]["brier"]],
                                    "fixed": [F.grade(b, "po")["all"]["brier"], F.grade(b, "ch")["all"]["brier"]]}
res["refit"] = {"u": bu, "sh": bsh}
res["n_leagues"] = {"train": len({r["lid"] for r in train}), "test": len({r["lid"] for r in test})}
json.dump(res, open(B + "/e32_fix.json", "w"), indent=1)
for name in ("train", "test"):
    for k, v in res[name].items():
        if k.startswith("season"): print(name, k, v); continue
        print(name, k, "po", {c: (x["brier"], x["ll"]) for c, x in v["po"].items()}, "ch", {c: (x["brier"], x["ll"]) for c, x in v["ch"].items()})

# Last regular-season week (display week = pws-1, record through pws-2): the shipped League page (simLeague) has no
# future matchups and falls back to `L.remWeeks||6` = 6 extra RANDOM weeks; simTitle plays 0 weeks; v116 plays the
# current week's real game.
def rnd6(recs):
    out = []; g = np.random.default_rng(5)
    for r in recs:
        r2 = dict(r); n = r["n"]; wk = []
        for _ in range(6):
            o = g.permutation(n); wk.append([(int(o[i]), int(o[i + 1])) for i in range(0, n - 1, 2)])
        r2["fut"] = wk; out.append(r2)
    return out
L_ = {}
for name, f in (("train", F.TR), ("test", lambda r: not F.TR(r))):
    rr = [r for r in F.RL if f(r)]
    L_[name] = {"n_leagues": len(rr), "page_shipped_6random": summ(F.run(rnd6(rr), u=.04, sh=.5)),
                "title_shipped_0wk": summ(F.run(drop_cur(rr), u=.04, sh=.5)), "fixed": summ(F.run(rr, u=.04, sh=.5, med=True))}
    for k, v in L_[name].items():
        if k != "n_leagues": print("LAST WEEK", name, k, "po", v["po"]["all"], "ch", v["ch"]["all"])
res["last_week"] = L_
# baselines (empirical rate by standings / points-for rank, fitted on 2022-23) and the median-league subset
res["baselines_test"] = {"standings_rank": summ(F.baseline(train, test, 0)), "pf_rank": summ(F.baseline(train, test, 1))}
for name, recs in (("train", train), ("test", test)):
    M = [r for r in recs if r["med"]]
    res[f"median_{name}"] = {"n_leagues": len({r['lid'] for r in M}), "shipped": summ(F.run(drop_cur(M), u=.04, sh=.5)),
                             "fixed": summ(F.run(M, u=.04, sh=.5, med=True))}
    print("MEDIAN", name, res[f"median_{name}"]["n_leagues"], {k: (res[f"median_{name}"][k]["po"]["all"]["brier"], res[f"median_{name}"][k]["ch"]["all"]["brier"]) for k in ("shipped", "fixed")})
for k, v in res["baselines_test"].items(): print("BASE", k, v["po"]["all"], v["ch"]["all"])
json.dump(res, open(B + "/e32_fix.json", "w"), indent=1)
