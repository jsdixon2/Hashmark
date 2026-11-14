p="index.html";s=open(p).read()
R=[('stash=ty!=="redraft"?fas.filter(p=>p.age&&p.age<=24&&p.brk!=null)','stash=ty!=="redraft"?fas.filter(p=>p.age&&p.age<=24&&p.brk!=null&&!p.broke)'),
('<span class="pill ${p.brk>.5?"hot":""}">${pc(p.brk)} breakout</span>','<span class="pill ${!p.broke&&p.brk>.5?"hot":""}">${p.broke?"Arrived":pc(p.brk)+" breakout"}</span>'),
('filter(x=>PL[x.id]&&(PL[x.id].brk||0)>=.1/* v121: honest odds, 10%+ only */)','filter(x=>PL[x.id]&&!PL[x.id].broke&&(PL[x.id].brk||0)>=.1/* v121: honest odds, 10%+ only; p175: not already broken out */)'),
('let tr=[];try{tr=allTrends();}catch(e){}const trd=tr.filter(x=>PL[x.id])','let tr=[];try{tr=allTrends();}catch(e){}const trd=tr.filter(x=>PL[x.id]&&!PL[x.id].broke)'),
('${Math.abs(dp)<3?"Same as market":','${Math.abs(dp)<3?(dp===0?"Same as market":"Within 3% of market"):')]
for a,b in R:
    assert s.count(a)==1,a[:60];s=s.replace(a,b)
open(p,"w").write(s);print("p175 ok")
