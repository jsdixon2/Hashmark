#!/usr/bin/env python3
"""e20 step 1: live player projections at in-game checkpoints vs final points (fit 2023-24, test 2025).
shipped (v66): so_far + pre x share_left.   blend: so_far + share_left x (k*pre + so_far)/(k + elapsed)
(Bayesian rate: pregame rate counts like k of a game; k per position), optional game-script term on margin."""
import gzip, json, csv, collections, sys
OUT = ".build/agents/b10/"
CK = {2: .1, 4: .2, 5: .25, 6: .3, 8: .4, 10: .5, 12: .6, 14: .7, 15: .75, 16: .8, 18: .9}
POSS = ("QB", "RB", "WR", "TE")
import os
PRE = os.environ.get("PRE", "hm")   # pregame projection: hm = Hashmark's (proj_panel replay, what the app uses), sl = Sleeper

def load():
    D = json.load(gzip.open(OUT + "pbp_cum.json.gz", "rt"))
    SP = json.load(gzip.open("bt/sleeper_proj.json.gz", "rt"))["w"]
    g2s, pos, pfr = {}, {}, {}
    for r in csv.DictReader(open("backtest/dl/ids.csv", encoding="utf-8")):
        sid = str(r["sleeper_id"]).split(".")[0]
        if r["gsis_id"] not in ("", "NA") and sid not in ("", "NA"): g2s[r["gsis_id"]] = sid; pos[r["gsis_id"]] = r["position"]
        if r["pfr_id"] not in ("", "NA") and r["gsis_id"] not in ("", "NA"): pfr[r["pfr_id"]] = r["gsis_id"]
    HMP = json.load(gzip.open(OUT + "hm_proj.json.gz", "rt")) if PRE == "hm" else {}
    rows = []
    for s in ("2023", "2024", "2025"):
        G = D[s]["G"]
        played = {}
        for r in csv.DictReader(open(f"backtest/dl/snap_{s}.csv")):
            if r["game_type"] != "REG" or float(r["offense_snaps"] or 0) <= 0: continue
            g = pfr.get(r["pfr_player_id"])
            if g: played[(r["week"], g)] = (r["game_id"], r["team"])
        keys = set(played) | {(w, g) for w, d in D[s].items() if w != "G" for g in d}
        for w, g in sorted(keys):
            p = pos.get(g)
            if p not in POSS: continue
            sid = g2s.get(g); P = SP.get(f"{s}-{w}") or {}
            if sid not in P or P[sid].get("pts_ppr") is None: continue
            pre = float(P[sid]["pts_ppr"])
            if PRE == "hm":
                h = HMP.get(f"{s}-{w}-{sid}")
                if h is None: continue
                pre = h
            if pre < 3: continue
            d = D[s].get(w, {}).get(g)
            if d is None:
                gid, t = played[(w, g)]; gi = G.get(gid)
                if not gi: continue
                sg = 1 if t == gi["h"] else -1
                d = {"g": gid, "t": t, "c": [0.0] * 21, "m": [sg * v for v in gi["m"]]}
            rows.append({"s": int(s), "w": int(w), "pos": p, "sid": sid, "gid": d["g"], "t": d["t"], "pre": pre, "c": d["c"], "m": d["m"]})
    return rows

def pred(r, i, k=None, gs=0.0):
    e = CK.get(i, i / 20); rem = max(.02, 1 - e); c = r["c"][i]; pre = r["pre"]
    if k is None: return c + pre * rem
    rate = (k * pre + c) / (k + e)
    return c + rem * max(0.0, rate) * (1 + gs * r["m"][i] / 10)

def mae(rs, i, **kw): return sum(abs(r["c"][20] - pred(r, i, **kw)) for r in rs) / len(rs)

def main():
    rows = load()
    tr = [r for r in rows if r["s"] <= 2024]; te = [r for r in rows if r["s"] == 2025]
    print("n train", len(tr), "test", len(te), file=sys.stderr)
    K = {}; GS = {}
    for p in POSS:
        rs = [r for r in tr if r["pos"] == p]
        best = None
        for k in [x / 20 for x in range(1, 61)] + [4, 5, 6, 8, 10, 15, 20, 50, 1e6]:
            v = sum(mae(rs, i, k=k) for i in CK)
            if best is None or v < best[0] - 1e-9: best = (v, k)
        K[p] = best[1]
        bg = None
        for g in [x / 100 for x in range(-30, 31, 2)]:
            v = sum(mae(rs, i, k=K[p], gs=g) for i in CK)
            if bg is None or v < bg[0] - 1e-9: bg = (v, g)
        GS[p] = bg[1]
    res = {"k": K, "gs": GS, "n_train": len(tr), "n_test": len(te), "ck": {}}
    for i, e in CK.items():
        row = {"e": e}
        for nm, kw in (("shipped", {}), ("blend", "B"), ("blend_gs", "G")):
            def f(r):
                if kw == "B": return pred(r, i, k=K[r["pos"]])
                if kw == "G": return pred(r, i, k=K[r["pos"]], gs=GS[r["pos"]])
                return pred(r, i)
            row[nm] = round(sum(abs(r["c"][20] - f(r)) for r in te) / len(te), 3)
            row[nm + "_pos"] = {p: round(sum(abs(r["c"][20] - f(r)) for r in te if r["pos"] == p) / max(1, sum(r["pos"] == p for r in te)), 3) for p in POSS}
        res["ck"][str(e)] = row
    # bias by pace (test season): pace = so_far / (pre * elapsed)
    bias = {}
    for i in (5, 10, 15):
        e = CK[i]; b = collections.defaultdict(lambda: [0, 0.0, 0.0])
        for r in te:
            pace = r["c"][i] / (r["pre"] * e)
            lab = "zero" if r["c"][i] <= 0 else "<0.5x" if pace < .5 else "0.5-1x" if pace < 1 else "1-1.5x" if pace < 1.5 else "1.5-2.5x" if pace < 2.5 else ">2.5x"
            x = b[lab]; x[0] += 1; x[1] += r["c"][20] - pred(r, i); x[2] += r["c"][20] - pred(r, i, k=K[r["pos"]])
        bias[str(e)] = {l: {"n": v[0], "shipped": round(v[1] / v[0], 2), "blend": round(v[2] / v[0], 2)} for l, v in b.items()}
    res["bias"] = bias
    json.dump(res, open(OUT + f"e20_player_{PRE}.json", "w"), indent=1)
    print(json.dumps({"k": K, "gs": GS}))
    print("e     shipped blend blend_gs")
    for e, row in res["ck"].items(): print(e, row["shipped"], row["blend"], row["blend_gs"])
    for e, v in bias.items(): print("bias", e, v)

if __name__ == "__main__":
    main()
