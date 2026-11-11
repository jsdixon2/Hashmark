"""e28: injury and practice multipliers in hmProj, measured. Replayed Hashmark projection BEFORE any multiplier
(proj_panel formula, props blended first like the app), for player-weeks where the player PLAYED, grouped by the
final NFL injury report (bt/nfl/injuries: report_status x practice_status). Also how often listed players sat.
Fit (weighted median of actual/projection, = MAE-optimal multiplier) on 2021-24, check 2025-26."""
import csv, gzip, json, os, sys, collections, statistics as stt
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT); sys.path.insert(0, os.path.join(ROOT, "scripts"))
import proj_panel as PP

def inj_map():
    g2s = {}
    for r in csv.DictReader(open(PP._get("ids.csv", PP.IDS), encoding="utf-8")):
        s = str(r.get("sleeper_id") or "").split(".")[0]
        if s not in ("", "NA") and r.get("gsis_id") not in ("", "NA", None): g2s[r["gsis_id"]] = s
    M = {}
    for y in range(2021, 2027):
        for r in csv.DictReader(gzip.open(f"bt/nfl/injuries/{y}.csv.gz", "rt")):
            if r.get("game_type", "REG") != "REG" or r["gsis_id"] not in g2s: continue
            rs = r.get("report_status") or ""; ps = r.get("practice_status") or ""
            ps = "DNP" if "Did Not" in ps else "LP" if "Limited" in ps else "FP" if "Full" in ps else ""
            M[(int(r["season"]), int(r["week"]), g2s[r["gsis_id"]])] = (rs, ps, r["position"])
    return M

def panel():
    C, PW = PP.load_app()
    rows = PP.build(range(2021, 2027), feats=True)
    M = inj_map()
    for r in rows:
        raw = PP.proj(C[r["pos"]], r["base"], r["ppg"], r["l3"], r["xs"], r["x3"], r["rk"], r["imp"])
        if r["mk"] is not None: pw = PW.get(r["pos"], .2); raw = raw * (1 - pw) + r["mk"] * pw
        r["pre"] = raw
        rs, ps, _ = M.get((r["s"], r["w"], r["pid"]), ("", "", ""))
        r["rs"], r["ps"] = rs, ps
    return rows, M

def wmed(R, k="pre"):  # multiplier m minimizing sum |a - m*pre|: weighted median of a/pre, weights pre
    xs = sorted(((r["a"] / r[k], r[k]) for r in R if r[k] > 0))
    tot = sum(w for _, w in xs); c = 0
    for v, w in xs:
        c += w
        if c >= tot / 2: return v
    return None

def mae(R, f): return sum(abs(r["a"] - f(r)) for r in R) / len(R) if R else float("nan")

def grp(r):
    return (r["rs"] or "none") + "/" + (r["ps"] or "-")

def main():
    rows, M = panel()
    R = [r for r in rows if r["pre"] >= 3]
    print("rows (played, pre>=3):", len(R))
    out = {"groups": {}, "sat": {}}
    TR = lambda r: r["s"] <= 2024; TE = lambda r: r["s"] >= 2025
    hdr = f"{'group':22s} {'pos':4s} {'n_tr':>5s} {'mult_tr':>7s} {'n_te':>5s} {'mult_te':>7s} {'sum a/pre':>9s} {'med':>5s} {'mean':>5s} {'a/sleeper':>9s} {'sl_wmed':>7s}"
    print(hdr)
    base_tr = wmed([r for r in R if TR(r) and not r["rs"] and r["ps"] in ("", "FP")])
    base_te = wmed([r for r in R if TE(r) and not r["rs"] and r["ps"] in ("", "FP")])
    print("healthy (no game status, full/no practice) multiplier: train", round(base_tr, 3), "test", round(base_te, 3))
    keys = ["none/-", "none/FP", "none/LP", "none/DNP", "Questionable/FP", "Questionable/LP", "Questionable/DNP", "Questionable/*", "Doubtful/*"]
    for g in keys:
        for pos in ("ALL", "QB", "RB", "WR", "TE"):
            sel = [r for r in R if (grp(r) == g or (g.endswith("/*") and r["rs"] == g.split("/")[0])) and (pos == "ALL" or r["pos"] == pos)]
            tr = [r for r in sel if TR(r)]; te = [r for r in sel if TE(r)]
            if len(sel) < 15: continue
            rat = [r["a"] / r["pre"] for r in sel]
            d = {"n_tr": len(tr), "m_tr": wmed(tr) if len(tr) >= 10 else None, "n_te": len(te), "m_te": wmed(te) if len(te) >= 10 else None,
                 "sum": sum(r["a"] for r in sel) / sum(r["pre"] for r in sel), "med": stt.median(rat), "mean": stt.mean(rat),
                 "a_sl": sum(r["a"] for r in sel) / sum(r["base"] for r in sel), "sl_wmed": wmed(sel, "base")}
            out["groups"][f"{g}|{pos}"] = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in d.items()}
            f = lambda v: f"{v:7.3f}" if v is not None else "      -"
            print(f"{g:22s} {pos:4s} {d['n_tr']:5d} {f(d['m_tr'])} {d['n_te']:5d} {f(d['m_te'])} {d['sum']:9.3f} {d['med']:5.2f} {d['mean']:5.2f} {d['a_sl']:9.3f} {f(d['sl_wmed'])}")
    # how often listed players sat out (fantasy positions, any projection): stats gp
    STS = json.load(gzip.open("bt/sleeper_stats.json.gz", "rt"))["w"]
    c = collections.Counter(); n = collections.Counter()
    for (y, w, s), (rs, ps, pos) in M.items():
        if pos not in ("QB", "RB", "WR", "TE") or f"{y}-{w}" not in STS: continue
        if rs not in ("Questionable", "Doubtful"): continue
        st = STS[f"{y}-{w}"].get(s) or {}
        played = bool(st.get("gp"))
        for k in (rs, f"{rs}/{ps or '-'}", f"{rs}|{'TR' if y <= 2024 else 'TE'}"):
            n[k] += 1; c[k] += played
    print("\nshare who PLAYED when listed:")
    for k in sorted(n):
        print(f"  {k:28s} n={n[k]:5d} played {c[k]/n[k]:.3f}"); out["sat"][k] = {"n": n[k], "played": round(c[k] / n[k], 3)}
    json.dump(out, open(".build/agents/b3/e28_inj.json", "w"), indent=1)
    return rows

if __name__ == "__main__": main()
