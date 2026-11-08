import pickle, pandas as pd, sys, os
R, M = pickle.load(open(sys.argv[1], "rb")); R = pd.DataFrame(R); M = pd.DataFrame(M)
print("team-weeks", len(R), "leagues", R[["lg", "s"]].drop_duplicates().shape[0], "seasons", R.s.value_counts().to_dict())
for th in [None, 4, 8, 12]:
    q = R if th is None else R[R.g > th]
    print(f"Hashmark {'all' if th is None else 'rated '+str(th)+'+'}: n={len(q)} gain {q.r3.mean():.2f} helped {(q.r3>0).mean():.3f} hurt {(q.r3<0).mean():.3f}")
for typ in ["waiver", "free_agent"]:
    q = M[M.typ == typ]; print(f"managers {typ}: n={len(q)} gain {q.r3.mean():.2f} helped {(q.r3>0).mean():.3f} hurt {(q.r3<0).mean():.3f}")
print(f"managers' adds Hashmark rated 4+: {M[M.g>4].r3.mean():.2f} (n={len(M[M.g>4])}); rated <=0: {M[M.g<=0].r3.mean():.2f} (n={len(M[M.g<=0])})")
