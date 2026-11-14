p="index.html";s=open(p).read()
a='''const guide=stash||need?`<section class="pan mt"><h2>Free agent guide</h2><div class="list mt">${need?g("Thinnest spot: "+need,fas.filter(p=>p.pos===need).sort((a,b)=>s4(b)-s4(a))[0],"Best available "+need):""}${stash?g("Stash",stash,`${PCT(stash.brk)}% breakout odds`):""}</div></section>`:"";'''
b='''const gin=(need?g("Thinnest spot: "+need,fas.filter(p=>p.pos===need).sort((a,b)=>s4(b)-s4(a))[0],"Best available "+need):"")+(stash?g("Stash",stash,`${PCT(stash.brk)}% breakout odds`):""),guide=gin?`<section class="pan mt"><h2>Free agent guide</h2><div class="list mt">${gin}</div></section>`:"";'''
assert s.count(a)==1;s=s.replace(a,b);open(p,"w").write(s);print("p177 ok")
