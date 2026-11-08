"""Analysis of e11_trades.pkl: does the v68 'fits both plans' rule pick trades that turned out well for both teams?"""
import pandas as pd, numpy as np, os, json
B = os.path.dirname(os.path.abspath(__file__))
D = pd.read_pickle(B + "/e11_trades.pkl")
D = D[D.fut_0.notna() & D.fut_1.notna()].copy()          # need the one-year-later market check
LU, AGE = .3, 1.5
def fits(plan, lu, ag_in, ag_out, vets, npk, lu_t=LU, age_t=AGE, vet_ok=False):
    if plan == "contender": return lu >= lu_t
    if plan == "rebuilding": return (vet_ok or vets == 0) and (npk > 0 or ag_in <= ag_out - age_t)
    return True
def ben(plan, now, fut):
    if plan == "contender": return now > 0
    if plan == "rebuilding": return fut > 0
    return fut > 0 or now > .5
def side(i): return D[[c for c in D.columns if c.endswith(f"_{i}")]].rename(columns=lambda c: c[:-2])
S = pd.concat([side(0).assign(t=D.index, mg=D.mg, s=D.s, typ=D.typ), side(1).assign(t=D.index, mg=-D.mg, s=D.s, typ=D.typ)])
S["fit"] = [fits(*r) for r in zip(S.plan, S.lu, S.ag_in, S.ag_out, S.vets, S.npk)]
S["ben"] = [ben(*r) for r in zip(S.plan, S.now, S.fut)]
out = {}
print(f"{len(D)} trades (in-season, 2-team, offense, dynasty+keeper, 2022-25 with a one-year-later value check)")
print("plans:", S.plan.value_counts().to_dict())
print("\n1) each side: did it benefit by its own plan? (fits the v68 rule vs not)")
for pl in ["contender", "rebuilding", "middle"]:
    q = S[S.plan == pl]; a, b = q[q.fit], q[~q.fit]
    msr = "lineup pts/wk rest of season > 0" if pl == "contender" else "value 1 yr later > 0" if pl == "rebuilding" else "either"
    print(f"  {pl:10s} ({msr}): fits {a.ben.mean():.1%} (n={len(a)}) | doesn't fit {b.ben.mean():.1%} (n={len(b)})"
          + (f" | avg lineup gain {a.now.mean():+.2f} vs {b.now.mean():+.2f}" if pl == "contender" else f" | avg value change {a.fut.mean():+.1%} vs {b.fut.mean():+.1%}" if pl == "rebuilding" else ""))
    out[pl] = dict(fit=round(a.ben.mean(), 3), nofit=round(b.ben.mean(), 3), n_fit=len(a), n_nofit=len(b))
# rebuilders: the two parts of the rule
r = S[S.plan == "rebuilding"]
print(f"  rebuilders who took on ageing veterans: {r[r.vets>0].ben.mean():.1%} benefited (n={(r.vets>0).sum()}), value {r[r.vets>0].fut.mean():+.1%}; no veterans: {r[r.vets==0].ben.mean():.1%} (n={(r.vets==0).sum()}), value {r[r.vets==0].fut.mean():+.1%}")
for s_ in (2022, 2023, 2024):
    q = S[S.s == s_]
    print(f"    {s_}: contender fits {q[(q.plan=='contender')&q.fit].ben.mean():.1%} vs {q[(q.plan=='contender')&~q.fit].ben.mean():.1%} | rebuilder fits {q[(q.plan=='rebuilding')&q.fit].ben.mean():.1%} vs {q[(q.plan=='rebuilding')&~q.fit].ben.mean():.1%}")
r = S[(S.plan == "rebuilding") & S.nxt.notna()]
print(f"  rebuilders, actual PPR points NEXT season of players received minus sent (players only, 2022-24 trades):")
print(f"    fits {r[r.fit].nxt.mean():+.0f} pts, positive {(r[r.fit].nxt>0).mean():.1%} (n={r.fit.sum()}) | doesn't fit {r[~r.fit].nxt.mean():+.0f}, positive {(r[~r.fit].nxt>0).mean():.1%} (n={(~r.fit).sum()})")
rp = r[(r.npk == 0)]
print(f"    player-only trades (no picks): fits {rp[rp.fit].nxt.mean():+.0f}, positive {(rp[rp.fit].nxt>0).mean():.1%} (n={rp.fit.sum()}) | doesn't fit {rp[~rp.fit].nxt.mean():+.0f}, positive {(rp[~rp.fit].nxt>0).mean():.1%} (n={(~rp.fit).sum()})")
print(f"    took on ageing veterans: {r[r.vets>0].nxt.mean():+.0f} pts next season (n={(r.vets>0).sum()}) vs none {r[r.vets==0].nxt.mean():+.0f}")
r2 = S[(S.plan == "rebuilding") & S.nxt2.notna()]; r2p = r2[r2.npk == 0]
print(f"  rebuilders, PPR points TWO seasons later (2022-23 trades): fits {r2[r2.fit].nxt2.mean():+.0f}, positive {(r2[r2.fit].nxt2>0).mean():.1%} (n={r2.fit.sum()}) | doesn't fit {r2[~r2.fit].nxt2.mean():+.0f}, positive {(r2[~r2.fit].nxt2>0).mean():.1%} (n={(~r2.fit).sum()})")
print(f"    player-only: fits {r2p[r2p.fit].nxt2.mean():+.0f}, positive {(r2p[r2p.fit].nxt2>0).mean():.1%} (n={r2p.fit.sum()}) | doesn't fit {r2p[~r2p.fit].nxt2.mean():+.0f}, positive {(r2p[~r2p.fit].nxt2>0).mean():.1%} (n={(~r2p.fit).sum()})")
print(f"    took on ageing veterans: {r2[r2.vets>0].nxt2.mean():+.0f} two seasons later (n={(r2.vets>0).sum()}) vs none {r2[r2.vets==0].nxt2.mean():+.0f}")
c2 = S[(S.plan == "contender") & S.nxt.notna()]
print(f"  contenders, next-season points of players received minus sent: fits {c2[c2.fit].nxt.mean():+.0f} vs doesn't {c2[~c2.fit].nxt.mean():+.0f}")
out["rebuild_two_seasons"] = dict(fit=round(float(r2[r2.fit].nxt2.mean()), 1), nofit=round(float(r2[~r2.fit].nxt2.mean()), 1))
out["rebuild_next_season"] = dict(fit=round(float(r[r.fit].nxt.mean()), 1), nofit=round(float(r[~r.fit].nxt.mean()), 1))
print("\n2) whole trades: both sides benefited by their own plan")
T = S.groupby("t").agg(both=("ben", "all"), fitboth=("fit", "all"), anyb=("ben", "any"))
T["fair"] = D.mg.abs().reindex(T.index) <= .2
for lab, m in [("all real trades", T.index == T.index), ("fit both plans + fair market (v68 rule)", T.fitboth & T.fair), ("fair market, but don't fit both", ~T.fitboth & T.fair), ("don't fit both", ~T.fitboth)]:
    q = T[m]; print(f"  {lab:42s} both benefited {q.both.mean():.1%}  (n={len(q)})"); out["both_" + lab] = dict(rate=round(q.both.mean(), 3), n=len(q))
# trades between a contender and a rebuilder: the classic case
cr = S.groupby("t").plan.agg(lambda x: tuple(sorted(x)))
m = cr == ("contender", "rebuilding")
q = T[m.reindex(T.index)]
print(f"  contender <-> rebuilder trades: fit both {q[q.fitboth].both.mean():.1%} (n={q.fitboth.sum()}) vs not {q[~q.fitboth].both.mean():.1%} (n={(~q.fitboth).sum()})")
print("\n3) thresholds: contender lineup gain, rebuilder age margin")
for lt in (0, .3, 1, 2, 3):
    q = S[S.plan == "contender"]; f = q.lu >= lt; print(f"  contender lineup gain >= {lt}: benefited {q[f].ben.mean():.1%} (n={f.sum()}), avg {q[f].now.mean():+.2f} pts/wk")
for at in (0, 1, 1.5, 2, 3):
    q = S[S.plan == "rebuilding"]; f = [fits("rebuilding", 0, a, b, v, k, age_t=at) for a, b, v, k in zip(q.ag_in, q.ag_out, q.vets, q.npk)]; f = np.array(f)
    print(f"  rebuilder younger by >= {at} yrs or adds a pick, no vets: benefited {q[f].ben.mean():.1%} (n={f.sum()}), value {q[f].fut.mean():+.1%}")
json.dump(out, open(B + "/e11.json", "w"), indent=1)
