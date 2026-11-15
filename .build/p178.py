# p178 (owner: The Wire waiver stories are repetitive): one waiver roundup story per league instead of one per big bid;
# the doubled team tag "Audric Estime NO (NO)" is gone (C.pn already shows the team).
p = "index.html"; s = open(p).read()
end = 'pr:50+Math.min(20,t.bid/2)});}'
assert s.count(end) == 1
i = s.index('  for(const t of recent.filter(t=>t.type==="waiver"&&t.bid>0).sort((a,b)=>b.bid-a.bid).slice(0,2)){')
j = s.index(end, i) + len(end)
new = '''  /* p178: one roundup story for the recent paid claims instead of one story per bid */
  {const cl=recent.filter(t=>t.type==="waiver"&&t.bid>0&&Object.keys(t.adds||{}).length).sort((a,b)=>b.bid-a.bid);
  if(cl.length){const t=cl[0],[p,r]=Object.entries(t.adds||{})[0];let pts=0,starts=0,wks=0;
    x.weeks.forEach((wk,i)=>{if(i+1<t.wk||i+1>=C.pws)return;const m=wk.find(q=>+q.rid===+r);if(!m)return;wks++;if((m.st||[]).includes(p)){starts++;pts+=+((m.pp||{})[p])||0;}});const q=PL[p]||{};
    const wk0=Math.min(...cl.map(c=>c.wk)),wk1=Math.max(...cl.map(c=>c.wk)),tot=cl.reduce((a,c)=>a+c.bid,0),mx=b=>med?` (${(b/med).toFixed(1)}×)`:"";
    const rows=cl.slice(1,6).map(c=>{const [pp,rr]=Object.entries(c.adds)[0];return [`${tn(rr)}`,`${hxName(pp)} · $${c.bid}${mx(c.bid)}`];});
    push({tag:"Waivers",cls:"",head:cl.length>1?`Waiver wire: ${tn(r)} lead${tn(r)==="You"?"":"s"} the spending with $${t.bid} on ${hxName(p)}`:`${tn(r)} spend${tn(r)==="You"?"":"s"} $${t.bid} on ${hxName(p)}`,
      lead:`${cl.length>1?`${cl.length} paid claims ${wk0===wk1?`in week ${wk1}`:`in weeks ${wk0}–${wk1}`}, $${tot} spent in all. `:""}The biggest: ${tn(r)} won ${C.pn(p)} for $${t.bid}, ${med?`${(t.bid/med).toFixed(1)}× the league's typical winning bid of $${med}`:"the top bid"}.`,
      facts:[med?["League's median winning bid",`$${med}`]:null,wks?[`${hxName(p)} started since`,`${starts} of ${wks} week${wks===1?"":"s"} · ${f1(pts)} pts`]:null,q.ros?[`${hxName(p)} projection`,`${f1(q.ros)} pts a week rest of season`]:null,...rows].filter(Boolean),
      det:[q.inj?`${hxName(p)} injury status: ${q.inj}.`:null,C.ppg(p)?`${hxName(p)} averages ${f1(C.ppg(p))} points a game when he plays.`:null].filter(Boolean),when:wk0===wk1?`Week ${wk1}`:`Weeks ${wk0}–${wk1}`,pr:50+Math.min(20,t.bid/2)});}}'''
s = s[:i] + new + s[j:]
open(p, "w").write(s); print("p178 ok")
