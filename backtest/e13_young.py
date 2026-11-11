"""Engine 3 retest (v106): does the Hashmark production model undervalue young players in dynasty values?
Owner question (2026-11-11): Germie Bernard (rookie WR, ~#123 in every dynasty market) showed 955, well below the market,
because the production model (20% of the Superflex dynasty blend) looks 2 seasons ahead from current points per game.
Setup, each season 2021-24 at the early-November market date (hv.json.gz, FantasyPros dynasty SF / redraft SF ECR):
  market  = curve(dynasty SF rank)          (app: 60% market group)
  redraft = curve(redraft SF rank)          (app: 20%)
  model   = curve(rank of hmModelVal)       (app: 20%; stats through week 8, xFP blended, measured age curves)
Outcomes: (1) market value one year later (same date next season), (2) real points above replacement over the next two
seasons (2021-23 dates). Values compared on the app's 0-10,000 curve. Groups: young = age <= 23.5 at the date.
Variants: model weight, model horizon/discount for young players, a "years of data" gate. Output e13_young.json."""
import csv, gzip, json, math, os, statistics as st
from collections import defaultdict
B=os.path.dirname(os.path.abspath(__file__)); R=os.path.dirname(B)
VANS=[[1,10000],[2,9766],[3,9548],[6,8960],[12,7959],[18,7114],[24,6382],[36,5178],[50,4093],[75,2732],[100,1849],[150,870],[200,421],[300,103],[450,14],[600,5]]
def curve(r):
    if r<=1: return 10000
    for (r1,v1),(r2,v2) in zip(VANS,VANS[1:]):
        if r<=r2:
            t=(math.log(r)-math.log(r1))/(math.log(r2)-math.log(r1)); return math.exp(math.log(v1)+t*(math.log(v2)-math.log(v1)))
    return 5
AGE={"QB":[[22,.87],[23,.95],[24,.98],[25,.97],[32,.97],[33,.93],[34,.9],[35,.85],[36,.78],[37,.7],[38,.6],[39,.5],[40,.4]],
 "RB":[[21,.82],[22,.88],[23,.96],[24,1],[25,.96],[26,.92],[27,.85],[28,.77],[29,.69],[30,.54],[31,.46],[32,.38],[33,.3]],
 "WR":[[21,.73],[22,.85],[23,.96],[24,.97],[25,1],[26,.93],[27,.89],[28,.82],[29,.74],[30,.65],[31,.58],[32,.48],[33,.41],[34,.35],[35,.3]],
 "TE":[[21,.85],[23,.9],[25,1],[29,1],[30,.93],[31,.86],[32,.78],[33,.7],[35,.55]]}
def am(pos,a):
    t=AGE[pos]
    if a<=t[0][0]: return t[0][1]
    for (x0,y0),(x1,y1) in zip(t,t[1:]):
        if a<=x1: return y0+(y1-y0)*(a-x0)/(x1-x0)
    return t[-1][1]
REPL={"QB":11.5,"RB":10.5,"WR":11,"TE":9}; ROOK={"QB":9,"RB":8,"WR":6,"TE":4.5}
def model(pos,age,ppg,xfp,yrs=2,disc=.65,xw=.5):
    if ppg is None: ppg=ROOK[pos]
    elif xfp is not None: ppg=(1-xw)*ppg+xw*xfp
    base=ppg/max(.3,am(pos,age)); v=max(0,ppg-REPL[pos])*17
    for y in range(1,yrs+1): v+=max(0,base*am(pos,age+y)-REPL[pos])*17*disc**y
    return v
# ids
ids={};g2s={}
for r in csv.DictReader(open(f"{B}/dl/ids.csv")):
    if r["sleeper_id"] in ("","NA") or r["position"] not in AGE: continue
    ids[r["sleeper_id"]]=r
    if r["gsis_id"] not in ("","NA"): g2s[r["gsis_id"]]=r["sleeper_id"]
# weekly points + xfp
pts=defaultdict(dict); xf=defaultdict(dict)
for y in range(2021,2026):
    for r in csv.DictReader(open(f"{B}/dl/pw_{y}.csv")):
        if r["season_type"]!="REG": continue
        s=g2s.get(r["player_id"])
        if s: pts[(s,y)][int(r["week"])]=float(r["fantasy_points_ppr"] or 0)
    for r in csv.DictReader(open(f"{B}/dl/ep_{y}.csv")):
        s=g2s.get(r["player_id"])
        try: xf[(s,y)][int(r["week"])]=float(r["total_fantasy_points_exp"] or 0)
        except: pass
hv=json.load(gzip.open(f"{R}/bt/hv.json.gz")); H=hv["ids"]
def ranks(date,key):
    i=hv["d"].index(date); return {H[j]:k+1 for k,j in enumerate(hv["t"][key][i])}
DATES={2021:"2021-11-05",2022:"2022-11-04",2023:"2023-11-03",2024:"2024-11-01",2025:"2025-11-07"}
def age_at(r,date):
    try: by=r["birthdate"]; return (int(date[:4])-int(by[:4]))+(int(date[5:7])-int(by[5:7]))/12
    except: return None
rows=[]
for y in (2021,2022,2023,2024):
    D=DATES[y]; mk=ranks(D,"dsf"); rd=ranks(D,"rsf"); nx=ranks(DATES[y+1],"dsf")
    univ=sorted(set(mk)|{s for (s,yy) in pts if yy==y})
    cand=[]
    for s in univ:
        r=ids.get(s)
        if not r: continue
        a=age_at(r,D)
        if a is None: continue
        wk={w:p for w,p in pts.get((s,y),{}).items() if w<=8}; xw_={w:p for w,p in xf.get((s,y),{}).items() if w<=8}
        ppg=st.mean(wk.values()) if len(wk)>=3 else None; xfp=st.mean(xw_.values()) if len(xw_)>=3 and ppg is not None else None
        if ppg is None:   # last season
            ly=pts.get((s,y-1),{})
            if len(ly)>=3: ppg=st.mean(ly.values())
        dy=r["draft_year"]; exp=y-int(dy) if dy not in ("","NA") else 5
        fut=[]
        for k in (1,2):
            z=pts.get((s,y+k),{}); fut.append(sum(max(0,v) for v in z.values())-REPL[r["position"]]*len(z) if z else 0)
        cand.append(dict(s=s,pos=r["position"],age=a,exp=exp,ppg=ppg,xfp=xfp,mk=mk.get(s),rd=rd.get(s),nx=nx.get(s),par=max(0,fut[0])+.65*max(0,fut[1]),y=y,prodok=y<=2023))
    rows+=cand
print(len(rows),"player-dates")
def rank_vals(xs,key):   # rank by key desc within year -> curve
    by=defaultdict(list)
    for x in xs: by[x["y"]].append(x)
    for y,L in by.items():
        L.sort(key=lambda x:(-x[key],x["s"]))
        i=0
        while i<len(L):   # ties share their average rank (many players tie at 0)
            j=i
            while j+1<len(L) and L[j+1][key]==L[i][key]: j+=1
            for x in L[i:j+1]: x[key+"_v"]=curve((i+j)/2+1)
            i=j+1
def run(name,wmk=.6,wrd=.2,wmd=.2,young_yrs=None,young_disc=None,gate=None,young_w=None,young_rd=None,yage=23.5):
    for x in rows:
        yrs,disc=2,.65
        if young_yrs and x["age"]<=yage: yrs=young_yrs; disc=young_disc or disc
        x["m"]=model(x["pos"],x["age"],x["ppg"],x["xfp"],yrs,disc)
    rank_vals(rows,"m")
    out=[]
    for x in rows:
        if x["mk"] is None or x["mk"]>300: continue
        wm=wmd
        if young_w is not None and x["age"]<=23.5: wm=young_w
        if gate is not None and x["exp"]<gate: wm=0
        wr=wrd
        if young_rd is not None and x["age"]<=yage: wr=young_rd
        v_mk=curve(x["mk"]); v_rd=curve(x["rd"]) if x["rd"] else curve(450)
        pred=(wmk*v_mk+wr*v_rd+wm*x["m_v"])/(wmk+wr+wm)
        out.append((x,pred))
    return out
for x in rows: x["nxv"]=curve(x["nx"]) if x["nx"] else 5
rank_vals(rows,"par")
def score(out,grp):
    sel=[(x,p) for x,p in out if grp(x)]
    a=[p-x["nxv"] for x,p in sel]; pr=[(x,p) for x,p in sel if x["prodok"]]
    b=[p-x["par_v"] for x,p in pr]
    sp=lambda L,k:spearman([p for _,p in L],[x[k] for x,_ in L])
    return dict(n=len(sel),bias_mkt=round(st.mean(a)),mae_mkt=round(st.mean(map(abs,a))),rho_mkt=round(sp(sel,"nxv"),3),
                n_prod=len(pr),bias_prod=round(st.mean(b)),mae_prod=round(st.mean(map(abs,b))),rho_prod=round(sp(pr,"par_v"),3))
def spearman(a,b):
    def rk(v):
        o=sorted(range(len(v)),key=lambda i:v[i]); r=[0]*len(v)
        for k,i in enumerate(o): r[i]=k
        return r
    ra,rb=rk(a),rk(b); n=len(a); ma=sum(ra)/n; mb=sum(rb)/n
    c=sum((x-ma)*(y-mb) for x,y in zip(ra,rb)); return c/math.sqrt(sum((x-ma)**2 for x in ra)*sum((y-mb)**2 for y in rb))
G={"all":lambda x:True,"young<=23.5":lambda x:x["age"]<=23.5,"rookie/2nd yr":lambda x:x["exp"]<=1,"older":lambda x:x["age"]>23.5,
   "young WR mkt 80-200":lambda x:x["age"]<=23.5 and x["pos"]=="WR" and 80<=x["mk"]<=200}
V={"app (mk .6 / rd .2 / model .2)":{},"market only":dict(wrd=0,wmd=0),"no model (mk .75 / rd .25)":dict(wmd=0,wrd=.25,wmk=.75),
   "model 0 for young":dict(young_w=0),"model .1 for young":dict(young_w=.1),
   "young: 4 yrs ahead":dict(young_yrs=4),"young: 4 yrs, disc .8":dict(young_yrs=4,young_disc=.8),
   "model 0 until 2nd season done":dict(gate=2),
   "young: this-season .1":dict(young_rd=.1),"young: this-season 0":dict(young_rd=0),
   "young: this-season .1 + 4 yrs disc .8":dict(young_rd=.1,young_yrs=4,young_disc=.8),
   "young: this-season 0 + 4 yrs disc .8":dict(young_rd=0,young_yrs=4,young_disc=.8),
   "<=24.5: this-season .1 + 4 yrs disc .8":dict(young_rd=.1,young_yrs=4,young_disc=.8,yage=24.5)}
res={}
for name,kw in V.items():
    out=run(name,**kw); res[name]={g:score(out,f) for g,f in G.items()}
    print(f"\n{name}")
    for g,s in res[name].items(): print(f"  {g:22s} n={s['n']:4d} mkt+1y bias {s['bias_mkt']:+5d} mae {s['mae_mkt']:4d} rho {s['rho_mkt']:.3f} | prod n={s['n_prod']:4d} bias {s['bias_prod']:+5d} mae {s['mae_prod']:4d} rho {s['rho_prod']:.3f}")
json.dump(res,open(f"{B}/e13_young.json","w"),indent=1)
