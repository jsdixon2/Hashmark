p="index.html";s=open(p).read()
R=[('''  <section class="pan mt"><h2>Lineup</h2><div class="chips mt">${(L.rpos||[]).map(x=>`<span class="tag">${esc(x.replace("_"," "))}</span>`).join(" ")}</div></section>
  <section class="pan mt"><h2>Settings</h2><div class="list mt">${kv("Waiver budget",''',
'''  ${(L.rpos||[]).length?`<section class="pan mt"><h2>Lineup</h2><div class="chips mt">${(L.rpos||[]).map(x=>`<span class="tag">${esc(x.replace("_"," "))}</span>`).join(" ")}</div></section>`:""}
  ${(st174=>st174?`<section class="pan mt"><h2>Settings</h2><div class="list mt">${st174}</div></section>`:"")(`${kv("Waiver budget",'''),
('''${kv("Draft rounds",s.draft_rounds)}</div></section>''','''${kv("Draft rounds",s.draft_rounds)}`)}'''),
('''["Started since",`${starts} of ${wks} week${wks===1?"":"s"} · ${f1(pts)} pts`]''','''wks?["Started since",`${starts} of ${wks} week${wks===1?"":"s"} · ${f1(pts)} pts`]:null''')]
for a,b in R:
    assert s.count(a)==1,a[:50];s=s.replace(a,b)
open(p,"w").write(s);print("p174 ok")
