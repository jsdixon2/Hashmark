"""Builds data/nfl.json from open sources. Run nightly (see .github/workflows/data.yml).
nflverse stats: CC-BY 4.0 (nflverse.com). IDs and ECR/values: DynastyProcess open data (github.com/dynastyprocess/data)."""
import csv,io,json,os,statistics,sys,urllib.request,datetime
def get(u):
    with urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"hashmark-build"}),timeout=120) as r: return r.read().decode("utf-8")
def rows(u): return csv.DictReader(io.StringIO(get(u)))
NV="https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_%d.csv"
DP="https://raw.githubusercontent.com/dynastyprocess/data/master/files/"
ids={r["gsis_id"]:r for r in rows(DP+"db_playerids.csv") if r["gsis_id"]!="NA" and r["sleeper_id"]!="NA"}
vals={r["fp_id"]:r for r in rows(DP+"values.csv")}
f=lambda x:float(x) if x not in(None,"","NA") else 0.0
out={};wk={}
for y in range(2018,datetime.date.today().year+1):
    try: data=list(rows(NV%y))
    except Exception as e: print("skip",y,e,file=sys.stderr); continue
    for r in data:
        if r.get("season_type")!="REG" or r["player_id"] not in ids: continue
        i=ids[r["player_id"]]["sleeper_id"];p=f(r.get("fantasy_points_ppr"))
        o=out.setdefault(i,{"s":{}});s=o["s"].setdefault(str(y),[0,0,0,0])
        s[0]+=1;s[1]+=p;s[2]+=f(r.get("targets"));s[3]+=f(r.get("carries"))+f(r.get("attempts"))*0
        wk.setdefault(i,[]).append(p)
for g,r in ids.items():
    i=r["sleeper_id"]
    if i not in out: continue
    o=out[i];o["pff"]=r["pff_id"];o["espn"]=r["espn_id"];v=vals.get(r["fantasypros_id"])
    if v: o.update(ecr1=f(v["ecr_1qb"]),ecr2=f(v["ecr_2qb"]),v1=f(v["value_1qb"]),v2=f(v["value_2qb"]))
    for s in o["s"].values(): s[1]=round(s[1],1)
    w=wk[i]; o["sd"]=round(statistics.pstdev(w),1) if len(w)>2 else None
os.makedirs("data",exist_ok=True)
json.dump({"asof":datetime.date.today().isoformat(),"p":out},open("data/nfl.json","w"),separators=(",",":"))
print(len(out),"players")
