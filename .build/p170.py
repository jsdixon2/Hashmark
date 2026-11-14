p="index.html";s=open(p).read()
a='const pt=e.target.closest("[data-ptab]");if(pt){S.ptab=pt.dataset.ptab;render();return;}'
b='const pt=e.target.closest("[data-ptab]");if(pt&&!pt.closest(".ptabs")){S.ptab=pt.dataset.ptab;render();return;}'
assert s.count(a)==1;s=s.replace(a,b);open(p,"w").write(s);print("p170 ok")
