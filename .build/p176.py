p="index.html";s=open(p).read()
a='`${ss.filter(s=>s.po).length} of ${ss.length} seasons in the playoffs`'
b='(ss.length?`${ss.filter(s=>s.po).length} of ${ss.length} seasons in the playoffs`:"First season in progress")'
assert s.count(a)==1;s=s.replace(a,b);open(p,"w").write(s);print("p176 ok")
