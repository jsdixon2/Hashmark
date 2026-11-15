# p179 (audit of The Wire playoff race story): the lead counted teams between 20% and 80% ("4 teams sit between ...")
# but w150Rewrite named everyone between 5% and 95% "on the bubble" (10 teams incl. 94%); and the details said both
# "A plays B next." and "B plays A next.". Rewrite now uses the same 20-80% band, adds "in good shape" (80-95%) and
# "long shots" (5-20%); matchups are listed once.
p = "index.html"; s = open(p).read()
R = [
 ('''else if(bub.length){s.lead=(s.lead||"")+` ${w150List(bub.map(r=>`${r.n} (${r.v})`))} ${bub.length>1?"are":"is"} on the bubble.`;}}''',
  '''else if(bub.length){const b2=rows.filter(r=>pct(r.v)>=.2&&pct(r.v)<=.8),gd=rows.filter(r=>pct(r.v)>.8&&pct(r.v)<.95),ls=rows.filter(r=>pct(r.v)>.05&&pct(r.v)<.2),z=[];
      if(b2.length)z.push(`${w150List(b2.map(r=>`${r.n} (${r.v})`))} ${b2.length>1?"are":"is"} on the bubble.`);if(gd.length)z.push(`${w150List(gd.map(r=>`${r.n} (${r.v})`))} ${gd.length>1?"are":"is"} in good shape.`);if(ls.length)z.push(`${w150List(ls.map(r=>`${r.n} (${r.v})`))} ${ls.length>1?"are long shots":"is a long shot"}.`);
      s.lead=(s.lead||"")+" "+z.join(" ");}}'''),
 ('''...bub.slice(0,4).map(q=>{const no=nextOpp(q.rid);return no?`${q.n} plays ${no.name} next.`:null;}).filter(Boolean)]''',
  '''...(sn=>bub.slice(0,4).map(q=>{const no=nextOpp(q.rid);if(!no||sn.has(no.name))return null;sn.add(q.n);return `${q.n} plays ${no.name} next.`;}).filter(Boolean))(new Set())]'''),
]
for a, b in R:
    assert s.count(a) == 1, a[:60]; s = s.replace(a, b)
open(p, "w").write(s); print("p179 ok")
