"""C4 leak check: is bt/sleeper_proj.json.gz a pre-kickoff record?
Compares the two archive versions git still holds (Nov 7 06:12 UTC = after week 9 TNF, before Sunday; Nov 10 10:01 UTC =
after week 9 MNF) and checks the post-game archive for late scratches and in-game injuries. Run from the repo root:
python3 backtest/e27_leak.py [old_archive.json.gz]  (default .build/agents/c4/old/sp_c78.json.gz = git show c78b2e6:...)."""
import csv, gzip, json, sys, statistics as st, collections
OLD = sys.argv[1] if len(sys.argv) > 1 else ".build/agents/c4/old/sp_c78.json.gz"
A = json.load(gzip.open(OLD, "rt")); B = json.load(gzip.open("bt/sleeper_proj.json.gz", "rt"))
ST = json.load(gzip.open("bt/sleeper_stats.json.gz", "rt"))["w"]
print("old built", A["built"], "| new built", B["built"])
s2g = {}; g2s = {}; tmid = {}
for r in csv.DictReader(open("backtest/dl/ids.csv", encoding="utf-8")):
    s = str(r["sleeper_id"]).split(".")[0]
    if s in ("", "NA") or r["gsis_id"] in ("", "NA"): continue
    s2g[s] = r["gsis_id"]; g2s[r["gsis_id"]] = s; tmid[s] = r["team"]
# 1) identical weeks?  any post-game revision between two post-game captures?
for k in sorted(set(A["w"]) & set(B["w"]), key=lambda k: tuple(map(int, k.split("-")))):
    a, b = A["w"][k], B["w"][k]
    ch = sum(1 for p in set(a) & set(b) if a[p] != b[p])
    if ch or set(a) != set(b): print("week", k, "changed", ch, "dropped", len(set(a) - set(b)), "added", len(set(b) - set(a)))
print("all other common weeks byte-identical:", sum(1 for k in set(A["w"]) & set(B["w"]) if A["w"][k] == B["w"][k]), "of", len(set(A["w"]) & set(B["w"])))
# 2) week 9: TNF game players (both captures post-game) vs Sun/Mon players (old = Saturday, new = post-game)
y, w = 2026, 9
kick = {}
for r in csv.DictReader(gzip.open("bt/nfl/schedules.csv.gz", "rt")):
    if r["season"] == "2026" and r["week"] == "9" and r["game_type"] == "REG":
        for t in (r["home_team"], r["away_team"]): kick[t] = r["gameday"] + " " + r["gametime"]
team = {}; inj = {}; snap = {}; usual = collections.defaultdict(list)
for r in csv.DictReader(gzip.open("bt/nfl/injuries/2026.csv.gz", "rt")):
    if r["week"] == "9" and r["gsis_id"] in g2s: inj[g2s[r["gsis_id"]]] = r["report_status"]; team[g2s[r["gsis_id"]]] = r["team"]
for r in csv.DictReader(gzip.open("bt/nfl/snaps/2026.csv.gz", "rt")):
    s = g2s.get(r["gsis_id"])
    if not s or r["game_type"] != "REG": continue
    pct = float(r["offense_pct"] or 0)
    if int(r["week"]) == 9: snap[s] = pct; team[s] = r["team"]
    elif int(r["week"]) < 9: usual[s].append(pct)
a, b = A["w"]["2026-9"], B["w"]["2026-9"]; S9 = ST.get("2026-9", {})
tnf = min(kick.values()); grp = collections.defaultdict(list)
for p in set(a) | set(b):
    t = team.get(p) or tmid.get(p); g = "TNF" if kick.get(t) == tnf else "SUN/MON"
    grp[g].append(p)
for g, ps in grp.items():
    both = [p for p in ps if p in a and p in b]
    ch = [p for p in both if abs(a[p]["pts_ppr"] - b[p]["pts_ppr"]) > .01]
    print(f"week 9 {g}: in both {len(both)}, changed {len(ch)}, only Saturday {sum(1 for p in ps if p in a and p not in b)}, only final {sum(1 for p in ps if p in b and p not in a)}")
    pl = [p for p in both if (S9.get(p) or {}).get("gp")]
    if g == "SUN/MON" and pl:
        act = lambda p: S9[p].get("pts_ppr") or 0
        print(f"  played n={len(pl)}: MAE Saturday {st.mean(abs(act(p) - a[p]['pts_ppr']) for p in pl):.3f}  final {st.mean(abs(act(p) - b[p]['pts_ppr']) for p in pl):.3f}  mean |change| {st.mean(abs(a[p]['pts_ppr'] - b[p]['pts_ppr']) for p in pl):.3f}")
        # in-game injury proxy: snap share < 60% of his usual (left early) vs the rest
        early = [p for p in pl if p in snap and len(usual[p]) >= 3 and st.mean(usual[p]) >= .5 and snap[p] < .6 * st.mean(usual[p])]
        rest = [p for p in pl if p not in early]
        d = lambda L: st.mean(b[p]["pts_ppr"] - a[p]["pts_ppr"] for p in L) if L else float("nan")
        print(f"  left early (snaps < 60% of usual) n={len(early)}: mean change Sat->final {d(early):+.2f}; others n={len(rest)} {d(rest):+.2f}")
        for p in sorted(early, key=lambda p: b[p]['pts_ppr'] - a[p]['pts_ppr']): print("    ", p, round(a[p]["pts_ppr"], 1), "->", round(b[p]["pts_ppr"], 1), "snaps", snap[p], "usual", round(st.mean(usual[p]), 2), "actual", S9[p].get("pts_ppr"))
        # changes vs outcome: does the Saturday->final move predict the Saturday miss beyond chance?
        x = [b[p]["pts_ppr"] - a[p]["pts_ppr"] for p in pl]; yv = [act(p) - a[p]["pts_ppr"] for p in pl]
        print(f"  corr(change, Saturday miss) {st.correlation(x, yv):.3f}")
    drop = [p for p in ps if p in a and p not in b]
    if drop: print("  dropped by final (zeroed):", sum(1 for p in drop if (S9.get(p) or {}).get("gp")), "of", len(drop), "played; statuses", collections.Counter(inj.get(p, "none") for p in drop))
# 3) whole post-game archive: players who did not play.  Pre-inactives captures would still list late scratches.
print("\npost-game archive, players with a projection >= .5 who did not play (gp=0), by season:")
outs = collections.defaultdict(set)
for yy in range(2021, 2027):
    for r in csv.DictReader(gzip.open(f"bt/nfl/injuries/{yy}.csv.gz", "rt")):
        if r["gsis_id"] in g2s and r["report_status"] in ("Out", "Doubtful", "Questionable"): outs[(yy, int(r["week"]), g2s[r["gsis_id"]])].add(r["report_status"])
for yy in range(2021, 2027):
    n = dnp = qdnp = qn = outp = 0
    for k, P in B["w"].items():
        s_, w_ = map(int, k.split("-"))
        if s_ != yy or k not in ST: continue
        for p, pr in P.items():
            if pr.get("pts_ppr", 0) < 3: continue
            n += 1; gp = (ST[k].get(p) or {}).get("gp"); stt = outs.get((yy, w_, p), set())
            if not gp: dnp += 1
            if "Out" in stt: outp += 1
            if "Questionable" in stt: qn += 1; qdnp += (not gp)
    print(f"  {yy}: proj>=3 n={n}  did not play {dnp} ({dnp / max(n, 1):.1%})  listed Out yet projected {outp}  questionable {qn}, of whom sat {qdnp} ({qdnp / max(qn, 1):.0%})")
# 4) size of late news: Saturday-listed Sun/Mon players (proj >= 1) who then did not play
print("\nweek 9 Saturday list, Sun/Mon games, proj >= 1:")
L = [p for p in grp["SUN/MON"] if p in a and a[p]["pts_ppr"] >= 1]
sat = [p for p in L if not (S9.get(p) or {}).get("gp")]
print(f"  n={len(L)}, did not play {len(sat)} ({len(sat) / len(L):.1%}), their Saturday proj mean {st.mean(a[p]['pts_ppr'] for p in sat) if sat else 0:.2f}, still in final archive {sum(1 for p in sat if p in b)}")
pl = [p for p in L if (S9.get(p) or {}).get("gp")]
act = lambda p: (S9.get(p) or {}).get("pts_ppr") or 0
print(f"  MAE Saturday proj over all {len(L)} (scratches count 0 pts): {st.mean(abs(act(p) - a[p]['pts_ppr']) for p in L):.3f} vs players who played only {st.mean(abs(act(p) - a[p]['pts_ppr']) for p in pl):.3f}")
