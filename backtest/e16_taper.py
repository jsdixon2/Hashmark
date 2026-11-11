"""A4: dynasty young-player adjustment (v107) - hard step at age 23 vs tapers, Superflex and 1QB.
v107 (from e13_young.py) gives players aged <= 23 (whole years, as Sleeper gives ages) a production model that looks
4 seasons ahead at .8 discount and halves the "this season" share (difference to the dynasty market). A player loses all
of it on his 24th birthday. This test compares that step with tapers w(age) in [0,1]:
  model value = w * model(4 yrs, .8) + (1-w) * model(base yrs/disc);  this-season share x (1 - R*w), rest to market.
Data: bt/hv.json.gz FantasyPros ECR history (dsf/do dynasty, ro redraft), early-November dates 2021-24; nflverse weekly
points + ffopportunity xFP (backtest/dl). Outcomes: (1) dynasty market value one year later, (2) real points above
replacement over the next two seasons (dates 2021-23), both on the app's 0-10,000 curve (VANS SF / VAN1 1QB).
NOTE on e13: hv has NO "rsf" (SF redraft) ranks at November dates (only preseason), so e13's this-season part was a
constant curve(450)=14 for every player. Here the this-season part is real: SF = November 1QB redraft ECR ("ro")
position ranks mapped onto overall ranks with the latest preseason SF redraft ("rsf") positional interleaving;
1QB = "ro" directly. Honest split: variants chosen on 2021-22 dates, reported on held-out 2023-24 (market) / 2023 (prod).
Output backtest/e16_taper.json."""
import csv, gzip, json, math, os, statistics as st
from collections import defaultdict
B=os.path.dirname(os.path.abspath(__file__)); R=os.path.dirname(B)
VANS=[[1,10000],[2,9766],[3,9548],[6,8960],[12,7959],[18,7114],[24,6382],[36,5178],[50,4093],[75,2732],[100,1849],[150,870],[200,421],[300,103],[450,14],[600,5]]
VAN1=[[1,10000],[2,9713],[3,9455],[6,8778],[12,7677],[18,6782],[24,6028],[36,4819],[50,3762],[75,2476],[100,1664],[150,782],[200,381],[300,98],[450,14],[600,5]]
def mkcurve(A):
    def c(r):
        if r<=1: return A[0][1]
        for (r1,v1),(r2,v2) in zip(A,A[1:]):
            if r<=r2:
                t=(math.log(r)-math.log(r1))/(math.log(r2)-math.log(r1)); return math.exp(math.log(v1)+t*(math.log(v2)-math.log(v1)))
        return 5
    return c
# app ageMult tables (AGE.TE as overridden in index.html)
AGE={"QB":[[22,.87],[23,.95],[24,.98],[25,.97],[32,.97],[33,.93],[34,.9],[35,.85],[36,.78],[37,.7],[38,.6],[39,.5],[40,.4]],
 "RB":[[21,.82],[22,.88],[23,.96],[24,1],[25,.96],[26,.92],[27,.85],[28,.77],[29,.69],[30,.54],[31,.46],[32,.38],[33,.3]],
 "WR":[[21,.73],[22,.85],[23,.96],[24,.97],[25,1],[26,.93],[27,.89],[28,.82],[29,.74],[30,.65],[31,.58],[32,.48],[33,.41],[34,.35],[35,.3]],
 "TE":[[21,.65],[22,.73],[23,.9],[24,.95],[25,1],[26,.95],[27,.91],[28,.86],[29,.8],[30,.72],[31,.66],[32,.58],[33,.5],[34,.42],[35,.35]]}
def am(pos,a):
    t=AGE[pos]
    if a<=t[0][0]: return t[0][1]
    for (x0,y0),(x1,y1) in zip(t,t[1:]):
        if a<=x1: return y0+(y1-y0)*(a-x0)/(x1-x0)
    return t[-1][1]
ROOK={"QB":9,"RB":8,"WR":6,"TE":4.5}
FMT={"sf":dict(dk="dsf",curve=mkcurve(VANS),REPL={"QB":11.5,"RB":10.5,"WR":11,"TE":9},yrs=2,disc=.65,W=(.6,.2,.2)),
     "1q":dict(dk="do",curve=mkcurve(VAN1),REPL={"QB":16,"RB":10.5,"WR":11,"TE":9},yrs=3,disc=.75,W=(.6,.25,.15))}
def model(pos,age,ppg,xfp,REPL,yrs,disc,xw=.5):
    if ppg is None: ppg=ROOK[pos]
    elif xfp is not None: ppg=(1-xw)*ppg+xw*xfp
    base=ppg/max(.3,am(pos,age)); v=max(0,ppg-REPL[pos])*17
    for y in range(1,yrs+1): v+=max(0,base*am(pos,age+y)-REPL[pos])*17*disc**y
    return v
ids={};g2s={}
for r in csv.DictReader(open(f"{B}/dl/ids.csv")):
    if r["sleeper_id"] in ("","NA") or r["position"] not in AGE: continue
    ids[r["sleeper_id"]]=r
    if r["gsis_id"] not in ("","NA"): g2s[r["gsis_id"]]=r["sleeper_id"]
pts=defaultdict(dict); xf=defaultdict(dict)
for y in range(2020,2026):
    for r in csv.DictReader(open(f"{B}/dl/pw_{y}.csv")) if os.path.exists(f"{B}/dl/pw_{y}.csv") else []:
        if r["season_type"]!="REG": continue
        s=g2s.get(r["player_id"])
        if s: pts[(s,y)][int(r["week"])]=float(r["fantasy_points_ppr"] or 0)
    for r in csv.DictReader(open(f"{B}/dl/ep_{y}.csv")) if os.path.exists(f"{B}/dl/ep_{y}.csv") else []:
        s=g2s.get(r["player_id"])
        try: xf[(s,y)][int(r["week"])]=float(r["total_fantasy_points_exp"] or 0)
        except: pass
hv=json.load(gzip.open(f"{R}/bt/hv.json.gz")); H=hv["ids"]
def order(date,key): i=hv["d"].index(date); return [H[j] for j in hv["t"][key][i]]
def ranks(date,key): return {s:k+1 for k,s in enumerate(order(date,key))}
DATES={2021:"2021-11-05",2022:"2022-11-04",2023:"2023-11-03",2024:"2024-11-01",2025:"2025-11-07"}
def sf_redraft(y):
    """November 'ro' position ranks placed on the overall ranks of the latest preseason SF redraft list ('rsf')."""
    pre=[d for i,d in enumerate(hv["d"]) if d<DATES[y] and hv["t"]["rsf"][i]][-1]
    slots=defaultdict(list)
    for k,s in enumerate(order(pre,"rsf")):
        if s in ids: slots[ids[s]["position"]].append(k+1)
    cnt=defaultdict(int); tmp=[]
    for s in order(DATES[y],"ro"):
        if s not in ids: continue
        p=ids[s]["position"]; L=slots[p]; k=cnt[p]; cnt[p]+=1
        tmp.append((L[k] if k<len(L) else 450+k,len(tmp),s))
    tmp.sort(); return {s:i+1 for i,(_,_,s) in enumerate(tmp)}
def age_at(r,date):
    try: by=r["birthdate"]; return (int(date[:4])-int(by[:4]))+(int(date[5:7])-int(by[5:7]))/12-(1 if int(date[5:7])==int(by[5:7]) and int(date[8:10])<int(by[8:10]) else 0)/12
    except: return None
def build(fmt):
    F=FMT[fmt]; rows=[]
    for y in (2021,2022,2023,2024):
        D=DATES[y]; mk=ranks(D,F["dk"]); rd=sf_redraft(y) if fmt=="sf" else ranks(D,"ro"); nx=ranks(DATES[y+1],F["dk"])
        univ=sorted(set(mk)|{s for (s,yy) in pts if yy==y})
        for s in univ:
            r=ids.get(s)
            if not r: continue
            a=age_at(r,D)
            if a is None: continue
            wk={w:p for w,p in pts.get((s,y),{}).items() if w<=8}; xw_={w:p for w,p in xf.get((s,y),{}).items() if w<=8}
            ppg=st.mean(wk.values()) if len(wk)>=3 else None; xfp=st.mean(xw_.values()) if len(xw_)>=3 and ppg is not None else None
            if ppg is None:
                ly=pts.get((s,y-1),{})
                if len(ly)>=3: ppg=st.mean(ly.values())
            fut=[]
            for k in (1,2):
                z=pts.get((s,y+k),{}); fut.append(sum(max(0,v) for v in z.values())-F["REPL"][r["position"]]*len(z) if z else 0)
            ai=math.floor(a+1e-9)  # whole years, as Sleeper gives
            m0=model(r["position"],ai,ppg,xfp,F["REPL"],F["yrs"],F["disc"]); m4=model(r["position"],ai,ppg,xfp,F["REPL"],4,.8)
            rows.append(dict(s=s,pos=r["position"],age=a,ai=ai,mk=mk.get(s),rd=rd.get(s),nx=nx.get(s),m0=m0,m4=m4,
                             par=max(0,fut[0])+.65*max(0,fut[1]),y=y,prodok=y<=2023))
    c=F["curve"]
    for x in rows: x["nxv"]=c(x["nx"]) if x["nx"] else 5
    rank_vals(rows,"par",c)
    return rows
def rank_vals(xs,key,c):
    by=defaultdict(list)
    for x in xs: by[x["y"]].append(x)
    for y,L in by.items():
        L.sort(key=lambda x:(-x[key],x["s"]))
        i=0
        while i<len(L):
            j=i
            while j+1<len(L) and L[j+1][key]==L[i][key]: j+=1
            for x in L[i:j+1]: x[key+"_v"]=c((i+j)/2+1)
            i=j+1
def taper(full,zero):   # w=1 at age<=full, linear to 0 at age>=zero (whole years)
    return lambda a: 1.0 if a<=full else 0.0 if a>=zero else (zero-a)/(zero-full)
SHAPES={"none":lambda a:0.0,"step<=23 (v107)":lambda a:1.0 if a<=23 else 0.0,
        "taper 22->25":taper(22,25),"taper 22->26":taper(22,26),"taper 23->26":taper(23,26),"taper 21->26":taper(21,26)}
def run(rows,fmt,shape,R=.5,model_on=True,constant_rd=False):
    F=FMT[fmt]; c=F["curve"]; wmk,wrd,wmd=F["W"]; f=SHAPES[shape]
    for x in rows:
        w=f(x["ai"]) if model_on else 0.0
        x["m"]=w*x["m4"]+(1-w)*x["m0"]
    rank_vals(rows,"m",c)
    out=[]
    for x in rows:
        if x["mk"] is None or x["mk"]>300: continue
        w=f(x["ai"]); wr=wrd*(1-R*w); wm_=wmk+(wrd-wr)
        v_rd=c(450) if constant_rd or not x["rd"] else c(x["rd"])
        out.append((x,(wm_*c(x["mk"])+wr*v_rd+wmd*x["m_v"])/(wm_+wr+wmd)))
    return out
def score(out,grp,yrs=None):
    sel=[(x,p) for x,p in out if grp(x) and (yrs is None or x["y"] in yrs)]
    if not sel: return dict(n=0)
    a=[p-x["nxv"] for x,p in sel]; pr=[(x,p) for x,p in sel if x["prodok"]]; b=[p-x["par_v"] for x,p in pr]
    return dict(n=len(sel),bias_mkt=round(st.mean(a)),mae_mkt=round(st.mean(map(abs,a))),
                n_prod=len(pr),bias_prod=round(st.mean(b)) if b else None,mae_prod=round(st.mean(map(abs,b))) if b else None)
GR={"all":lambda x:True,"<=23":lambda x:x["ai"]<=23,"24-26":lambda x:24<=x["ai"]<=26,**{f"age {a}":(lambda a:lambda x:x["ai"]==a)(a) for a in range(21,28)}}
res={}
def show(fmt,rows,name,**kw):
    out=run(rows,fmt,**kw); r={}
    for lab,yrs in (("pooled",None),("fit 21-22",{2021,2022}),("test 23-24",{2023,2024})):
        r[lab]={g:score(out,f,yrs) for g,f in GR.items()}
    res[f"{fmt} | {name}"]=r
    P=r["pooled"]; T=r["test 23-24"]
    line=" ".join(f"{a}:{P['age '+str(a)]['bias_mkt']:+5d}/{P['age '+str(a)]['mae_mkt']:4d}" for a in range(21,28))
    print(f"{fmt} {name:40s} all mkt {P['all']['mae_mkt']} prod {P['all']['mae_prod']} | <=23 mkt {P['<=23']['mae_mkt']} prod {P['<=23']['mae_prod']} | test all {T['all']['mae_mkt']}/{T['all']['mae_prod']} <=23 {T['<=23']['mae_mkt']}/{T['<=23']['mae_prod']}")
    print("     by age mkt bias/mae  "+line)
    print("     by age prod bias/mae "+" ".join(f"{a}:{P['age '+str(a)]['bias_prod']:+5d}/{P['age '+str(a)]['mae_prod']:4d}" for a in range(21,28)))
for fmt in ("sf","1q"):
    rows=build(fmt); print(f"\n=== {fmt}: {len(rows)} player-dates, scored (market top 300): {sum(1 for x in rows if x['mk'] and x['mk']<=300)}")
    if fmt=="sf": show(fmt,rows,"e13 replica: constant this-season, step",shape="step<=23 (v107)",constant_rd=True); show(fmt,rows,"e13 replica: constant this-season, none",shape="none",constant_rd=True)
    for sh in SHAPES:
        show(fmt,rows,sh,shape=sh)
    for sh in ("step<=23 (v107)","taper 22->25","taper 22->26","taper 23->26"):
        show(fmt,rows,sh+" model only",shape=sh,R=0)
        show(fmt,rows,sh+" this-season only",shape=sh,model_on=False)
        show(fmt,rows,sh+" this-season x0",shape=sh,R=1)
        show(fmt,rows,sh+" this-season x.75",shape=sh,R=.25)
json.dump(res,open(f"{B}/e16_taper.json","w"),indent=1)
