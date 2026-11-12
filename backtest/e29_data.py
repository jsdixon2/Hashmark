#!/usr/bin/env python3
"""e29: grading set for pregame win odds, 2021-2026 (every archived league matchup, regular season, not guillotine).
Team total = sum of the starters actually set (known after the fact; fine for calibration):
  old  = exactly what scripts/build_report.py does (full replayed projection for full-PPR leagues, simple hm() otherwise,
         no custom pass-TD / INT adjustment on the full projection)
  new  = full replayed projection in the league's own scoring (scripts/proj_panel.py scoring ppr/half/std) plus the league's
         pass-TD / INT difference from Sleeper's projected stats (same adjustment pts() applies); K/DST/IDP = Sleeper's projection
Writes .build/agents/a2/e29_rows.json: [season, week, league, teams, rec, old_a, old_b, new_a, new_b, won_a]."""
import gzip, json, collections, importlib.util, os, sys
sys.path.insert(0, "scripts")
spec = importlib.util.spec_from_file_location("br", "scripts/build_report.py"); BR = importlib.util.module_from_spec(spec); spec.loader.exec_module(BR)
spec = importlib.util.spec_from_file_location("pp", "scripts/proj_panel.py"); PP = importlib.util.module_from_spec(spec); spec.loader.exec_module(PP)
OUT = sys.argv[1] if len(sys.argv) > 1 else ".build/agents/a2/e29_rows.json"
C = BR.load_pjc(); POS = BR.positions()
SP = json.load(gzip.open("bt/sleeper_proj.json.gz", "rt"))["w"]
HM = {}
for sc in ("ppr", "half", "std"):
    for r in PP.build(range(2021, 2027), scoring=sc): HM[(sc, r["s"], r["w"], r["pid"])] = r["hm"]
    print(sc, "done", flush=True)
FK = {"ppr": "pts_ppr", "half": "pts_half_ppr", "std": "pts_std"}
def fmt(rec): return "ppr" if rec >= .75 else "half" if rec >= .25 else "std"
L = json.load(gzip.open("bt/leagues.json.gz", "rt"))["leagues"]
out = []
for lid in sorted(L):
    lg = L[lid]; s = int(lg["season"])
    if lg.get("guillotine") or s < 2021: continue
    sc = lg.get("sc") or {}; pws = lg.get("pws") or 15; rec = sc.get("rec", 1) or 0; f = fmt(rec)
    for wk in sorted(lg["weeks"], key=int):
        w = int(wk); P = SP.get(f"{s}-{w}")
        if not P or w >= pws: continue
        tot = {}
        for rid, mid, pt, st in lg["weeks"][wk]:
            hit = [x for x in st if x in P]
            if not st or len(hit) / len(st) < .9: continue
            old = sum(HM.get(("ppr", s, w, x)) if HM.get(("ppr", s, w, x)) is not None and rec >= .75 else BR.hm(BR.pts(P[x], sc), C.get(POS.get(x)), w) for x in hit)
            new = 0.0
            for x in hit:
                h = HM.get((f, s, w, x))
                new += BR.pts(P[x], sc) if h is None else h + BR.pts(P[x], sc) - (P[x].get(FK[f]) or 0)
            tot[rid] = (old, new, mid, pt)
        by = collections.defaultdict(list)
        for rid in sorted(tot):
            o, n, mid, pt = tot[rid]
            if mid is not None: by[mid].append((o, n, pt))
        for mid in sorted(by):
            pair = by[mid]
            if len(pair) != 2 or pair[0][2] == pair[1][2] or min(pair[0][2], pair[1][2]) <= 0: continue
            (oa, na, pa), (ob, nb, pb) = pair
            out.append([s, w, lid, lg.get("n") or 0, rec, round(oa, 3), round(ob, 3), round(na, 3), round(nb, 3), 1 if pa > pb else 0])
json.dump(out, open(OUT, "w")); print(len(out), collections.Counter(r[0] for r in out))
