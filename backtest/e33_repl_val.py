"""F1 / e33 item 2b: does the value model (hmModelVal; e16_taper replica, shipped v118 shape = taper 23->26, model only)
get more accurate with other replacement levels? Outcomes keep the shipped constants (points above the shipped level over
the next 2 seasons, and next-year dynasty market), only the model's replacement level changes. Fit/choose 2021-22,
held out 2023-24 (production: 2023 only)."""
import os, json
B = os.path.dirname(os.path.abspath(__file__))
src = open(B + "/e16_taper.py").read().split("res={}")[0]
src = src.replace('m0=model(r["position"],ai,ppg,xfp,F["REPL"],F["yrs"],F["disc"]); m4=model(r["position"],ai,ppg,xfp,F["REPL"],4,.8)',
                  'm0=model(r["position"],ai,ppg,xfp,MREPL[fmt],F["yrs"],F["disc"]); m4=model(r["position"],ai,ppg,xfp,MREPL[fmt],4,.8)')
assert "MREPL[fmt]" in src
ns = {"__file__": B + "/e16_taper.py"}; exec(src, ns)
CAND = {"shipped": {"sf": {"QB": 11.5, "RB": 10.5, "WR": 11, "TE": 9}, "1q": {"QB": 16, "RB": 10.5, "WR": 11, "TE": 9}},
        "ppg-measured (e33_repl sppg)": {"sf": {"QB": 13.3, "RB": 10.2, "WR": 11.5, "TE": 8.6}, "1q": {"QB": 17.1, "RB": 10.2, "WR": 11.5, "TE": 8.6}},
        "v114-scale (e33_repl hm)": {"sf": {"QB": 10.8, "RB": 8.9, "WR": 9.5, "TE": 7.8}, "1q": {"QB": 14.6, "RB": 8.9, "WR": 9.5, "TE": 7.8}}}
res = {}
for fmt in ("sf", "1q"):
    for name, C in CAND.items():
        ns["MREPL"] = C; rows = ns["build"](fmt)
        out = ns["run"](rows, fmt, shape="taper 23->26", R=0)
        r = {lab: {g: ns["score"](out, ns["GR"][g], yrs) for g in ("all", "<=23")} for lab, yrs in (("fit 21-22", {2021, 2022}), ("test 23-24", {2023, 2024}))}
        res[f"{fmt} | {name}"] = r
        f, t = r["fit 21-22"]["all"], r["test 23-24"]["all"]
        print(f"{fmt} {name:30s} fit mkt/prod {f['mae_mkt']}/{f['mae_prod']}  test mkt/prod {t['mae_mkt']}/{t['mae_prod']} (n {t['n']}/{t['n_prod']})", flush=True)
json.dump(res, open(B + "/e33_repl_val.json", "w"), indent=1)
