#!/usr/bin/env python3
"""bt/calib.json: league-wide weekly residual (actual team score minus Hashmark's archived-projection total), by season-week.
The app subtracts this from its own league's residuals, so what's left is the league's scoring-format effect
(bonuses, custom points) rather than how high-scoring that NFL week was."""
import csv, gzip, io, json, statistics, urllib.request

PJC = None
def load_pjc():
    import re
    s = open("index.html", encoding="utf-8").read()
    m = re.search(r"const PJC=(\{.*?\});", s)
    return json.loads(m.group(1))

def pts(st, sc):
    rec = sc.get("rec", 1)
    b = st.get("pts_ppr") if rec >= .75 else st.get("pts_half_ppr") if rec >= .25 else st.get("pts_std")
    if b is None: b = st.get("pts_ppr", 0) or 0
    if sc.get("pass_td") is not None and st.get("pass_td") is not None: b += (sc["pass_td"] - 4) * st["pass_td"]
    if sc.get("pass_int") is not None and st.get("pass_int") is not None: b += (sc["pass_int"] + 1) * st["pass_int"]
    return b

def main():
    C = load_pjc()
    txt = urllib.request.urlopen(urllib.request.Request("https://raw.githubusercontent.com/dynastyprocess/data/master/files/db_playerids.csv", headers={"User-Agent": "hashmark-build"}), timeout=60).read().decode()
    pos = {r["sleeper_id"].split(".")[0]: r["position"] for r in csv.DictReader(io.StringIO(txt)) if r.get("sleeper_id") not in ("", "NA")}
    SP = json.load(gzip.open("bt/sleeper_proj.json.gz", "rt"))["w"]
    L = json.load(gzip.open("bt/leagues.json.gz", "rt"))["leagues"]
    res = {}
    for lg in L.values():
        if lg.get("guillotine"): continue
        sc = lg.get("sc") or {}; pws = lg.get("pws") or 15
        for w, ws in lg["weeks"].items():
            w = int(w)
            if w >= pws: continue
            P = SP.get(f"{lg['season']}-{w}")
            if not P: continue
            for rid, mid, pt, st in ws:
                hit = [s for s in st if s in P]
                if not st or len(hit) / len(st) < .9: continue
                t = 0
                for s in hit:
                    v = pts(P[s], sc); c = C.get(pos.get(s))
                    if c: v = max(0, c[0] + sum(c[1:6]) * v + (0 if w <= 2 else c[8] + c[9]))
                    t += v
                if t > 30: res.setdefault(f"{lg['season']}-{w}", []).append(pt - t)
    out = {k: [round(statistics.mean(v), 2), len(v)] for k, v in sorted(res.items()) if len(v) >= 30}
    json.dump({"w": out, "k0": 12}, open("bt/calib.json", "w"), separators=(",", ":"))
    print(f"calib: {len(out)} weeks")

if __name__ == "__main__":
    main()
