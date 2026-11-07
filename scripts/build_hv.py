"""Historical consensus ranks by date (FantasyPros ECR via DynastyProcess, already mirrored in bt/nfl/ecr/), keyed by Sleeper id.
Lets the app grade a past trade by what the values were on the day it was made.
out: bt/hv.json.gz = {"ids":[sleeper ids], "d":[dates], "t":{"do":[[idx in rank order] per date], "dsf":..., "ro":..., "rsf":...}}"""
import pandas as pd, glob, gzip, json, io, os, urllib.request
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOP = {"do": 320, "dsf": 320, "ro": 260, "rsf": 260}
def ids():
    for u in ("https://raw.githubusercontent.com/dynastyprocess/data/master/files/db_playerids.csv", "https://github.com/dynastyprocess/data/raw/master/files/db_playerids.csv"):
        try:
            b = urllib.request.urlopen(u, timeout=60).read(); return pd.read_csv(io.BytesIO(b), low_memory=False)
        except Exception as e: print("ids:", e)
    raise SystemExit("no id table")
X = ids()[["fantasypros_id", "sleeper_id"]].dropna()
X["fantasypros_id"] = X.fantasypros_id.astype(float).astype(int).astype(str); X["sleeper_id"] = X.sleeper_id.astype(str).str.replace(r"\.0$", "", regex=True)
fp2s = dict(zip(X.fantasypros_id, X.sleeper_id))
files = sorted(glob.glob(f"{ROOT}/bt/nfl/ecr/*.csv.gz"))
frames = []
for f in files:
    d = pd.read_csv(f, dtype={"id": str}); d = d[d.ecr_type.isin(list(TOP)) & d.pos.isin(["QB", "RB", "WR", "TE"])]
    frames.append(d)
D = pd.concat(frames); D["sid"] = D.id.astype(str).str.replace(r"\.0$", "", regex=True).map(fp2s); D = D.dropna(subset=["sid"])
dates = sorted(D.scrape_date.unique())
# keep about two snapshots a month (the first scrape on/after the 1st and the 15th)
keep, last = [], None
for s in dates:
    half = s[:8] + ("a" if int(s[8:10]) < 15 else "b")
    if half != last: keep.append(s); last = half
D = D[D.scrape_date.isin(keep)]
idl, idx, T = [], {}, {k: [] for k in TOP}
for s in keep:
    q = D[D.scrape_date == s]
    for t, n in TOP.items():
        r = q[q.ecr_type == t].sort_values("ecr").drop_duplicates("sid").head(n)
        row = []
        for sid in r.sid:
            if sid not in idx: idx[sid] = len(idl); idl.append(sid)
            row.append(idx[sid])
        T[t].append(row)
out = {"ids": idl, "d": keep, "t": T, "src": "FantasyPros consensus (ECR) history via DynastyProcess"}
with gzip.open(f"{ROOT}/bt/hv.json.gz", "wt") as f: json.dump(out, f, separators=(",", ":"))
print(len(keep), "dates", keep[0], "->", keep[-1], len(idl), "players", os.path.getsize(f"{ROOT}/bt/hv.json.gz"), "bytes")
