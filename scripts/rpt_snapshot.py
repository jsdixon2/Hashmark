"""Report card: projections recorded BEFORE kickoff (key `projections_live`), graded against results.
Reads bt/proj_log/<season>-<week>.json.gz written by scripts/snapshot_proj.py (frozen per game at kickoff) and grades
each player against Sleeper's own final stat line (ctx["ST"] = bt/sleeper_stats.json.gz), the same way the replayed
panel is graded: players who played (gp > 0), PPR. Hashmark = the frozen projection; Sleeper = the frozen Sleeper
projection stored alongside it (the version on Sleeper when we recorded, not the later kickoff version).
A week is graded once its stats exist and its last game kicked off 8+ hours ago. Empty-safe."""
import glob, gzip, json, os, statistics as st
from datetime import datetime, timedelta, timezone

DIR = os.environ.get("HM_PROJ_LOG", "bt/proj_log")


def _mae(xs): return round(st.mean(xs), 3) if xs else None


def section(ctx):
    ST = ctx.get("ST")
    if ST is None:
        try: ST = json.load(gzip.open("bt/sleeper_stats.json.gz", "rt"))["w"]
        except Exception: ST = {}
    now = datetime.now(timezone.utc); weeks = []; rows = []; scr = []
    files = sorted(glob.glob(os.path.join(DIR, "*.json.gz")), key=lambda f: tuple(map(int, os.path.basename(f)[:-8].split("-"))))
    for f in files:
        try: d = json.load(gzip.open(f, "rt"))
        except Exception: continue
        key = f"{d['s']}-{d['w']}"; S = ST.get(key)
        if not S or not d.get("p"): continue
        last = max(datetime.strptime(v[0], "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc) for v in d["g"].values())
        if now - last < timedelta(hours=8): continue
        lead = [(datetime.strptime(d["g"][v[3]][0], "%Y-%m-%dT%H:%MZ") - datetime.strptime(d["g"][v[3]][1], "%Y-%m-%dT%H:%MZ")).total_seconds() / 3600
                for v in d["p"].values() if v[3] in d["g"]]
        W = []
        for pid, (hm, base, fl, g) in d["p"].items():
            s = S.get(pid)
            if s and s.get("gp"):
                a = s.get("pts_ppr") or 0; W.append((abs(a - hm), abs(a - base), fl))
            else:
                scr.append((hm, base))     # listed before kickoff, did not play (scratch / inactive): scores 0
        if not W: continue
        rows += W
        weeks.append({"s": d["s"], "w": d["w"], "n": len(W), "hm": _mae([x[0] for x in W]), "sl": _mae([x[1] for x in W]),
                      "scratch": sum(1 for pid in d["p"] if not (S.get(pid) or {}).get("gp")),
                      "lead_h": round(st.median(lead), 1) if lead else None})
    if not rows:
        return {"projections_live": {"n": 0, "weeks": 0}}
    allrows = [(x[0], x[1]) for x in rows] + [(h, b) for h, b in scr]
    q = [x for x in rows if x[2] & 1]
    return {"projections_live": {
        "since": {"s": weeks[0]["s"], "w": weeks[0]["w"]}, "weeks": len(weeks), "n": len(rows),
        "mae_hm": _mae([x[0] for x in rows]), "mae_sleeper": _mae([x[1] for x in rows]),
        "weeks_won": sum(1 for w in weeks if w["hm"] < w["sl"]),
        "with_scratches": {"n": len(allrows), "scratches": len(scr), "mae_hm": _mae([x[0] for x in allrows]), "mae_sleeper": _mae([x[1] for x in allrows])},
        "questionable": {"n": len(q), "mae_hm": _mae([x[0] for x in q]), "mae_sleeper": _mae([x[1] for x in q])},
        "by_week": weeks,
        "note": "recorded before kickoff (frozen per game), graded on players who played, PPR"}}


if __name__ == "__main__":
    print(json.dumps(section({}), indent=1)[:3000])
