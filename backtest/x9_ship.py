"""Build data/valpath.json for the calculator's value-over-time chart (v143) from backtest/x9_fit.json + bt/hv.json.gz.
cells: "lvl|fmt|pos|age|tier|phase|h" -> 11 quantiles of log(value later/now) (h 180/365/730/1095 only), bands widened by
K (x9_cal.py). picks: per fmt and pick bucket (rookie rank at the draft: r1e 1-4, r1m 4-9, r1l 9-12, r2 13-24, r3 25-36,
r4 37-60), values of real 2020-24 rookies 0.5/1.5/2.5 years after their draft (app 1QB/SF curve)."""
import json, sys, datetime as dt
K = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
exec(open("backtest/x9_paths.py").read().split("paths = []")[0])
F = json.load(open("backtest/x9_fit.json")); cells = {}
for k, (n, q) in F.items():
    if k.split("|")[-1] not in ("180", "365", "730", "1095"): continue
    m = q[5]; cells[k] = [round(m + K * (x - m), 3) for x in q]
BK = {"r1e": (0, 4), "r1m": (3, 9), "r1l": (8, 12), "r2": (12, 24), "r3": (24, 36), "r4": (36, 60)}
picks = {}
for f in FM:
    picks[f] = {}
    for b, (lo, hi) in BK.items():
        xs = [[], [], []]
        for Y in range(2020, 2025):
            j = near(dt.date(Y, 5, 20))
            if j is None or not RK[f][j]: continue
            rs = sorted([(r, p) for p, r in RK[f][j].items() if p in info and info[p][2] == str(Y)])[lo:hi]
            for r, p in rs:
                for n_, dd in enumerate((183, 548, 913)):
                    k = near(dt.date(Y, 5, 20) + dt.timedelta(days=dd))
                    if k is not None and RK[f][k]: xs[n_].append(round(val(f, k, p)))
        picks[f][b] = xs
json.dump({"v": 1, "K": K, "cells": cells, "picks": picks, "src": "FantasyPros dynasty consensus 2019-26 via DynastyProcess; backtest/x9"}, open("data/valpath.json", "w"), separators=(",", ":"))
import os; print("bytes", os.path.getsize("data/valpath.json"), "cells", len(cells), {f: {b: len(v[0]) for b, v in picks[f].items()} for f in picks})
