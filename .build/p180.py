# p180 (owner: Scout hub quick view didn't show the top-ranked players): the Devy Lab tile ranked the 2028+ classes
# together by devy score, while the Devy Lab page ranks each class by projected NFL pick. The tile now shows the class
# after the War Room's (ny+1) by projected pick, labelled with the class, matching that class's Devy Lab tab.
p = "index.html"; s = open(p).read()
a = '''const dvy=all.filter(p=>p.dclass>ny).sort((a,b)=>b.score-a.score).slice(0,4);top=dvy[0];dv=dvy.map(p=>mrow(`${p.pos} ${esc(p.n)}`,String(p.score),p.score,{go:"cfb-"+Object.keys(CFB.p).find(k=>CFB.p[k]===p)})).join("");'''
b = '''const dcl=ny+1,dvy=all.filter(p=>p.dclass===dcl&&p.proj).sort((a,b)=>a.proj.pick-b.proj.pick).slice(0,4);top=dvy[0];dv=dvy.map(p=>mrow(`${p.pos} ${esc(p.n)}`,p.proj.rd?`Rd ${p.proj.rd}`:"Day 3",null,{go:"cfb-"+Object.keys(CFB.p).find(k=>CFB.p[k]===p)})).join("");'''
assert s.count(a) == 1; s = s.replace(a, b)
a2 = '''${rtile("devy","devy","Devy Lab",top?esc(top.n):"College",top?`${top.pos} · ${esc(top.school)} · top devy score`:"loading prospects…",dv?`<div class="mcap">Devy score 0–100</div>${dv}`:"")}'''
b2 = '''${rtile("devy","devy","Devy Lab",top?esc(top.n):"College",top?`${top.pos} · ${esc(top.school)} · #1 in the ${ny+1} class`:"loading prospects…",dv?`<div class="mcap">${ny+1} class · projected draft round</div>${dv}`:"")}'''
assert s.count(a2) == 1; s = s.replace(a2, b2)
open(p, "w").write(s); print("p180 ok")
