"""e31 analysis: waiver advice on today's projections (input backtest/e31_exact.pkl from e31_exact.py).
Unit: real lineup points the move added over weeks w+1..w+3 (week w left out: some real adds were made after its games),
lineups set before each week by Hashmark's current weekly projection (r3h); helped > +1, hurt < -1, neutral between.
Shown move = the team-week's best logged pair by g' (lift - .25 x drop's 4-week points) if g' >= bar (4; 6 dynasty).
Candidate stricter rules for WR adds / dynasty: chosen on 2024, checked on 2025. Writes backtest/e31.json."""
import pickle, os, json, numpy as np, pandas as pd
B = os.path.dirname(os.path.abspath(__file__))
RA, MA, NT = pickle.load(open(B + "/e31_exact.pkl", "rb"))
R = pd.DataFrame(RA); M = pd.DataFrame(MA)
TN = {0: "redraft", 1: "keeper", 2: "dynasty", 3: "other"}
R["tn"] = R.t.map(TN); M["tn"] = M.t.map(TN)
R = R.sort_values(["s", "w", "lg", "rid", "gp", "a"], ascending=[True, True, True, True, False, True]).reset_index(drop=True)
R["share"] = np.where(R.ht > 0, R.hmax / R.ht.where(R.ht > 0, 1), 0)
R["close"] = R.dval >= .45 * R.aval.clip(lower=1)
KEY = ["s", "w", "lg", "rid"]
def st(q, c="r3h"):
    x = q[c]; n = len(q)
    if not n: return dict(n=0)
    return dict(n=int(n), pts=round(float(x.mean()), 2), helped=round(float((x > 1).mean()), 3), neutral=round(float(((x >= -1) & (x <= 1)).mean()), 3),
                hurt=round(float((x < -1).mean()), 3), total=round(float(x.sum()), 0))
def fmt(d): return f"n {d['n']:6d}  {d.get('pts', 0):+6.2f}  helped {d.get('helped', 0):.0%}  neutral {d.get('neutral', 0):.0%}  hurt {d.get('hurt', 0):.0%}  total {d.get('total', 0):8.0f}" if d["n"] else "n 0"
BAR = {"redraft": 4, "keeper": 4, "other": 4, "dynasty": 6}
def shown(rule=None, base=None):
    """team-week's best pair that passes the rule (rule(df) -> bool mask of allowed pairs); g' >= bar."""
    q = R if base is None else base
    ok = q.gp >= q.tn.map(BAR)
    if rule is not None: ok &= rule(q)
    q = q[ok]
    return q.loc[q.groupby(KEY).gp.idxmax()]
out = {"team_weeks": int(NT), "pairs": int(len(R)), "unit": "real lineup pts, weeks w+1..w+3, lineups set by Hashmark's weekly projection"}
S0 = shown()
print("== shipped rule (g' >= 4, 6 dynasty), lineups set by today's projection (r3h) | old measure r3s | hindsight r3")
base = {}
for tn in ["redraft", "keeper", "dynasty", "other"]:
    for s in (2024, 2025, "both"):
        q = S0[(S0.tn == tn) & ((S0.s == s) if s != "both" else True)]
        base[f"{tn} {s}"] = {"r3h": st(q), "r3s": st(q, "r3s"), "r3": st(q, "r3")}
        print(f"{tn:8s} {s}: {fmt(st(q))} | r3s {st(q,'r3s').get('pts')} hurt {st(q,'r3s').get('hurt')} | r3 {st(q,'r3').get('pts')}")
allf = S0[S0.tn != "other"]
print("all 3 formats both:", fmt(st(allf)))
print("\n== by add position (shown, both seasons)")
bypos = {}
for tn in ["redraft", "keeper", "dynasty"]:
    for p in ["QB", "RB", "WR", "TE"]:
        bypos[f"{tn} {p}"] = st(S0[(S0.tn == tn) & (S0.apos == p)]); print(f"{tn:8s} {p}: {fmt(bypos[f'{tn} {p}'])}")
for p in ["QB", "RB", "WR", "TE"]:
    for s in (2024, 2025): print(f"all {p} {s}: {fmt(st(allf[(allf.apos == p) & (allf.s == s)]))}")
print("\n== managers' own adds (single add, any drop)")
mgr = {}
for tn in ["redraft", "keeper", "dynasty", "other"]:
    for typ in ("waiver", "free_agent", "all"):
        q = M[(M.tn == tn) & ((M.typ == typ) if typ != "all" else True)]
        mgr[f"{tn} {typ}"] = st(q); print(f"{tn:8s} {typ:10s}: {fmt(st(q))} | r3 hindsight {st(q,'r3').get('pts')}")
    for s in (2024, 2025): print(f"   {s} waiver: {fmt(st(M[(M.tn == tn) & (M.typ == 'waiver') & (M.s == s)]))}")
    for p in ["QB", "RB", "WR", "TE"]: mgr[f"{tn} waiver {p}"] = st(M[(M.tn == tn) & (M.typ == "waiver") & (M.apos == p)])
print("managers by add pos (waiver, redraft):", {p: mgr[f'redraft waiver {p}'].get('pts') for p in "QB RB WR TE".split()})
out.update(base=base, by_pos=bypos, managers=mgr)

# ---------- candidate stricter rules ----------
C = {"shipped": None}
for x in (2, 4, 6, 8): C[f"WR bar +{x}"] = (lambda x: lambda q: (q.apos != "WR") | (q.gp >= q.tn.map(BAR) + x))(x)
for x in (2, 4, 6): C[f"dynasty bar +{x}"] = (lambda x: lambda q: (q.tn != "dynasty") | (q.gp >= BAR["dynasty"] + x))(x)
C["no close calls (drop >= 45% of add)"] = lambda q: ~q.close
C["WR: no close calls"] = lambda q: (q.apos != "WR") | ~q.close
C["dynasty: no close calls"] = lambda q: (q.tn != "dynasty") | ~q.close
for m in (2, 4, 6): C[f"add 4-wk pts >= drop's + {m}"] = (lambda m: lambda q: q.aval >= q.dval + m)(m)
for sh in (.35, .5): C[f"WR: best week < {int(sh*100)}% of season pts"] = (lambda sh: lambda q: (q.apos != "WR") | (q.hg < 2) | (q.share < sh))(sh)
for sh in (.3, .4, .45): C[f"WR: best week < {int(sh*100)}% of season pts"] = (lambda sh: lambda q: (q.apos != "WR") | (q.hg < 2) | (q.share < sh))(sh)
C["WR: needs 2+ games played"] = lambda q: (q.apos != "WR") | (q.hg >= 2)
C["WR & dynasty: no close calls"] = lambda q: ((q.apos != "WR") & (q.tn != "dynasty")) | ~q.close
C["WR bar +4 & dynasty: no close calls"] = lambda q: ((q.apos != "WR") | (q.gp >= q.tn.map(BAR) + 4)) & ((q.tn != "dynasty") | ~q.close)
cand = {}
print("\n== candidate rules: shown moves (3 formats) | WR adds | dynasty   [chosen on 2024, checked on 2025]")
for name, rule in C.items():
    S1 = shown(rule); S1 = S1[S1.tn != "other"]; cand[name] = {}
    for s in (2024, 2025):
        q = S1[S1.s == s]
        cand[name][s] = {"all": st(q), "WR": st(q[q.apos == "WR"]), "dynasty": st(q[q.tn == "dynasty"]), "redraft": st(q[q.tn == "redraft"]), "keeper": st(q[q.tn == "keeper"])}
    for s in (2024, 2025):
        c = cand[name][s]; print(f"{name:38s} {s} ALL {fmt(c['all'])}\n{'':38s}      WR  {fmt(c['WR'])}\n{'':38s}      DYN {fmt(c['dynasty'])}")
out["candidates"] = {k: {str(s): v for s, v in d.items()} for k, d in cand.items()}
json.dump(out, open(B + "/e31.json", "w"), indent=1)

# ---------- shipped in v115: WR adds whose best week is 45%+ of their season points (2+ games) don't count as a move ----------
# chosen on 2024 (largest total gain with hurt% not above shipped, among .3/.35/.4/.45/.5/.6), checked on 2025.
SPIKE = .45
rule = lambda q: (q.apos != "WR") | (q.hg < 2) | (q.share < SPIKE)
S1 = shown(rule)
final = {}
print("\n== before (v67 rule) -> after (v115 rule), lineups set by today's projection")
for tn in ["redraft", "keeper", "dynasty"]:
    for s in (2024, 2025, "both"):
        b = S0[(S0.tn == tn) & ((S0.s == s) if s != "both" else True)]; a = S1[(S1.tn == tn) & ((S1.s == s) if s != "both" else True)]
        final[f"{tn} {s}"] = {"before": st(b), "after": st(a), "before_WR": st(b[b.apos == "WR"]), "after_WR": st(a[a.apos == "WR"])}
        print(f"{tn:8s} {s}: before {fmt(st(b))}\n{'':15s}after  {fmt(st(a))}\n{'':15s}WR before {fmt(st(b[b.apos=='WR']))}\n{'':15s}WR after  {fmt(st(a[a.apos=='WR']))}")
for tn in ["redraft", "keeper", "dynasty"]:
    for p in ["QB", "RB", "WR", "TE"]: final[f"{tn} after {p}"] = st(S1[(S1.tn == tn) & (S1.apos == p)])
a3 = S1[S1.tn != "other"]; b3 = S0[S0.tn != "other"]
final["all3 both"] = {"before": st(b3), "after": st(a3)}
print("all 3 formats:", fmt(st(b3)), "->", fmt(st(a3)))
out["final"] = final; out["spike"] = SPIKE
json.dump(out, open(B + "/e31.json", "w"), indent=1)
