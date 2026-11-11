"""e28: candidate injury/practice multipliers for players who play, MAE on affected player-weeks per season."""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import e28_inj as E
rows, M = E.panel()
R = [r for r in rows if r["pre"] >= 3]
print("Questionable (played) weighted-median multiplier by season, vs healthy:")
for y in range(2021, 2027):
    q = [r for r in R if r["s"] == y and r["rs"] == "Questionable"]; h = [r for r in R if r["s"] == y and not r["rs"] and r["ps"] in ("", "FP")]
    d = [r for r in R if r["s"] == y and not r["rs"] and r["ps"] == "DNP"]
    print(f"  {y} Q n={len(q):3d} m={E.wmed(q):.3f} sum={sum(r['a'] for r in q)/sum(r['pre'] for r in q):.3f}  healthy m={E.wmed(h):.3f}  DNP-only n={len(d)} m={(E.wmed(d) or 0):.3f}")
def mk(q, dnp, lp, qp=None):
    def f(r):
        m = r["pre"]
        if r["rs"] == "Questionable": m *= q if qp is None else qp.get(r["ps"], q)
        elif r["rs"] == "Doubtful": m *= .35
        if qp is None or r["rs"] != "Questionable":
            if r["ps"] == "DNP": m *= dnp
            elif r["ps"] == "LP": m *= lp
        return m
    return f
tr = [r for r in R if r["s"] <= 2024 and r["rs"] == "Questionable"]
cell = {ps: E.wmed([r for r in tr if r["ps"] == ps]) for ps in ("FP", "LP", "DNP")}
dnp_only = E.wmed([r for r in R if r["s"] <= 2024 and not r["rs"] and r["ps"] == "DNP"])
print("fitted 2021-24: Q cells", {k: round(v, 3) for k, v in cell.items()}, "practice-only DNP", round(dnp_only, 3))
C = {"current (Q .88, DNP .9, LP .97 stacked)": mk(.88, .9, .97), "no multipliers": mk(1, 1, 1), "Q 1, DNP .9, LP 1": mk(1, .9, 1),
     "Q .95, DNP .9, LP 1": mk(.95, .9, 1), "Q .92, DNP .9, LP 1": mk(.92, .9, 1), "Q .88 only": mk(.88, 1, 1),
     "fitted cells": mk(1, dnp_only, 1, {k: round(v, 2) for k, v in cell.items()})}
aff = lambda r: r["rs"] in ("Questionable", "Doubtful") or r["ps"] in ("DNP", "LP")
for y in (2021, 2022, 2023, 2024, 2025, 2026, "2025-26"):
    S = [r for r in R if (r["s"] >= 2025 if y == "2025-26" else r["s"] == y)]; A = [r for r in S if aff(r)]
    Q = [r for r in S if r["rs"] == "Questionable"]
    print(f"\n{y}: affected n={len(A)} (Q {len(Q)}), all n={len(S)}")
    for k, f in C.items():
        print(f"  {k:40s} affected {E.mae(A, f):.4f}  Q {E.mae(Q, f):.4f}  all {E.mae(S, f):.4f}")

print("\nRolling-origin check: multipliers fitted on the 2 seasons before each test season (weighted median, played, pre>=3)")
def fitcells(T):
    q = {ps: E.wmed([r for r in T if r["rs"] == "Questionable" and r["ps"] == ps]) for ps in ("FP", "LP", "DNP")}
    qa = E.wmed([r for r in T if r["rs"] == "Questionable"])
    d = E.wmed([r for r in T if not r["rs"] and r["ps"] == "DNP"]); l = E.wmed([r for r in T if not r["rs"] and r["ps"] == "LP"])
    return qa, q, d, l
for y in (2023, 2024, 2025, 2026):
    T = [r for r in R if y - 2 <= r["s"] < y]; qa, q, d, l = fitcells(T)
    S = [r for r in R if r["s"] == y]; A = [r for r in S if aff(r)]
    f1 = mk(qa, d, l); f2 = mk(1, d, l, q); cur = C["current (Q .88, DNP .9, LP .97 stacked)"]; best = C["Q 1, DNP .9, LP 1"]
    print(f"  {y}: fit Q {qa:.3f} cells {{{', '.join(f'{k} {v:.2f}' for k,v in q.items())}}} DNP-only {d:.3f} LP-only {l:.3f} | affected n={len(A)} current {E.mae(A,cur):.4f}  fitted Q+practice {E.mae(A,f1):.4f}  fitted cells {E.mae(A,f2):.4f}  Q1/DNP.9 {E.mae(A,best):.4f}")

print("\nShipped candidate (Q .97 from the 2023-24 fit, practice-only DNP .9 kept, LP dropped):")
new = mk(.97, .9, 1); cur = C["current (Q .88, DNP .9, LP .97 stacked)"]
for y in (2023, 2024, 2025, 2026, "2025-26"):
    S = [r for r in R if (r["s"] >= 2025 if y == "2025-26" else r["s"] == y)]; A = [r for r in S if aff(r)]; Q = [r for r in S if r["rs"] == "Questionable"]
    Lp = [r for r in S if r["ps"] == "LP"]
    print(f"  {y}: affected n={len(A)} {E.mae(A,cur):.4f} -> {E.mae(A,new):.4f} | Q n={len(Q)} {E.mae(Q,cur):.4f} -> {E.mae(Q,new):.4f} | LP n={len(Lp)} {E.mae(Lp,cur):.4f} -> {E.mae(Lp,new):.4f} | all n={len(S)} {E.mae(S,cur):.4f} -> {E.mae(S,new):.4f}")
