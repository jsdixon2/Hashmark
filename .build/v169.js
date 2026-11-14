/* ===== v169 (owner: "avoid boring pages like this", GM > Moves was a list of links). Each move is now a card you can act
   on in place, built only from numbers the app already computes:
   - Sell high / Buy low / Buy before return / Trade target / Pre-breakout: the best built trade (tradeOpts) with its
     calculator grade (calcEval on a temporary S.calc), lineup change, market note and a Build button; "N more" opens
     the player's page with every option.
   - Free agent: big lineup gain, drop and bid (wireRecs) + a button to the waiver wire.
   - Lineup alerts with no bench fix ("check free agents"): the best free agent this week for that slot.
   Top 5 moves get cards; the rest fold under "N smaller moves". ===== */
function g169Grade(L,x){const mi=mineIdx(L),sv=S.calc;try{S.calc={lid:L.id,sides:[mi,x.c.ti],assets:x.send.map(a=>({k:"p",id:a.id,from:mi,to:x.c.ti})).concat(x.get.map(a=>({k:"p",id:a.id,from:x.c.ti,to:mi})))};
  const R=calcEval();const me=R&&R.find(r=>r.ti===mi);return me?me.g:null;}catch(e){return null;}finally{S.calc=sv;}}
function g169FA(L,m,used){const me=L.teams[mineIdx(L)];let slot=null,pos=null;const e=/^Empty (\S+) slot$/.exec(m.t);
  if(e){slot=Object.keys(ELIG).find(k=>slotLabel(k)===e[1])||e[1];}
  else{const p=me.players.map(id=>PL[id]).find(p=>p&&m.t.startsWith(p.name+" "));if(p)pos=p.pos;}
  const ok=slot&&ELIG[slot]?ELIG[slot]:pos?[pos]:null;if(!ok)return null;
  return freeAgents().filter(p=>ok.includes(p.pos)&&!locked(p)&&!lostSeason(p)&&wkProj(p)>0&&!(used&&used.has(p.id))).sort((a,b)=>wkProj(b)-wkProj(a))[0]||null;}
function g169Card(L,m,used){const pid=m.go&&m.go.startsWith("player-")?m.go.slice(7):null,p=pid?PL[pid]:null,mi=mineIdx(L);
  const head=`<div class="m169h"${pid?` data-go="player-${pid}" role="link"`:""}><span class="pill${m.pr>=80?" hot":""}">${esc(m.k)}</span><div class="m169t">${esc(m.t)}</div>${pid?CHEV:""}</div>`;
  let body=`<div class="s m169s">${esc(m.s)}</div>`,act="";
  try{
    if(p&&/Sell high|Buy|Trade target|Pre-breakout/.test(m.k)){const dir=m.k==="Sell high"?"sell":"buy",opts=tradeOpts(L,p,dir);
      if(opts.length){const x=opts[0],g=g169Grade(L,x),nm=a=>esc(a.p.name),enc=(a,f,to)=>[a.id,f,to];
        const mk=Math.abs(x.mg)<.03?"even market":x.mg>0?`market favors them ${Math.round(x.mg*100)}%`:`market favors you ${Math.round(-x.mg*100)}%`;
        act=`<div class="m169a"><div class="m169g">${g?`<b class="m169gr">${g}</b>`:""}<div style="min-width:0"><div class="m169d">Send ${x.send.map(nm).join(" + ")} · get ${x.get.map(nm).join(" + ")}</div>
          <div class="sub">${esc(x.c.t.name)} · you ${x.gMe>=0?"+":""}${f1(x.gMe)} pts/wk · ${mk}</div></div></div>
          <div class="m169b"><button class="btn sm" data-build='${esc(JSON.stringify({a:x.send.map(a=>enc(a,mi,x.c.ti)),b:x.get.map(a=>enc(a,x.c.ti,mi))}))}' data-bt="${x.c.ti}">Build trade</button>${opts.length>1?`<button class="btn ghost sm" data-go="player-${pid}">${opts.length-1} more option${opts.length>2?"s":""}</button>`:""}</div></div>`;}
      else act=`<div class="m169a"><div class="sub">No realistic trade built around him right now.</div><div class="m169b"><button class="btn ghost sm" data-go="${dir==="sell"?"trade-sell":"trade-buy"}">See ${dir==="sell"?"sell-high":"buy-low"} list</button></div></div>`;}
    else if(m.k==="Free agent"&&p){const r=wireRecs(L,6).find(r=>r.p.id===pid);
      if(r){act=`<div class="m169a"><div class="m169g"><b class="m169n">+${f1(r.g)}</b><div style="min-width:0"><div class="m169d">pts in your lineup over 4 weeks</div>
          <div class="sub">${r.d?`Drop ${esc(r.d.name)}`:"No drop needed"}${r.bid?` · bid $${r.bid.bid} (wins about ${Math.round(r.bid.win*100)}%)`:""}</div></div></div>
          <div class="m169b"><button class="btn sm" data-go="waivers">Waiver wire</button></div></div>`;body="";}}
    else if((m.k==="Urgent"||m.k==="Start/sit")&&/check free agents/.test(m.s)){const f=g169FA(L,m,used);
      if(f){if(used)used.add(f.id);let gm="";try{const gg=typeof g155==="function"?g155(f):null;gm=gg?" · "+gg:"";}catch(e){}
        body=`<div class="s m169s">No bench player can fill it.</div>`;act=`<div class="m169a"><div class="m169g"><b class="m169n">${f1(wkProj(f))}</b><div style="min-width:0"><div class="m169d">Best free agent: ${esc(f.name)}</div>
          <div class="sub">${esc(f.pos)} · ${esc(f.team)}${gm} · projected this week</div></div></div>
          <div class="m169b"><button class="btn sm" data-go="player-${f.id}">See ${esc(f.name.split(" ").slice(-1)[0])}</button><button class="btn ghost sm" data-go="roster">Roster</button></div></div>`;}}
  }catch(e){console.error(e);}
  return `<div class="m169">${head}${body}${act}</div>`;}
vGMMoves=(function(prev){return function(){const L=S.L;if(!L)return prev();let mv=[];try{mv=leagueDigest(L).mv;}catch(e){}
  if(!mv.length)return prev();const top=mv.slice(0,5),rest=mv.slice(5);
  const row=m=>`<button class="act" data-go="${m.go}"><span class="pill">${esc(m.k)}</span><span style="min-width:0"><div class="t">${esc(m.t)}</div><div class="s">${esc(m.s)}</div></span>${CHEV}</button>`;
  return `<p class="sub">Your best moves in ${esc(L.name)} this week, most urgent first.</p><div class="m169l mt">${(u=>top.map(m=>g169Card(L,m,u)).join(""))(new Set())}</div>${rest.length?`<details class="m169x mt"><summary>${rest.length} smaller move${rest.length>1?"s":""}</summary><section class="pan">${rest.map(row).join("")}</section></details>`:""}`;};})(vGMMoves);
document.head.insertAdjacentHTML("beforeend",`<style>
.m169l{display:flex;flex-direction:column;gap:10px}
.m169{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:14px}
.m169h{display:flex;align-items:center;gap:10px;cursor:pointer}.m169h .pill{flex:none}.m169t{font-weight:700;font-size:16px;flex:1;min-width:0}
.m169h svg{flex:none;opacity:.5}
.m169s{margin-top:6px}
.m169a{margin-top:10px;padding-top:10px;border-top:1px solid var(--line)}
.m169g{display:flex;gap:12px;align-items:center}.m169d{font-weight:600;font-size:14px}
.m169gr,.m169n{flex:none;min-width:44px;height:44px;padding:0 6px;border-radius:12px;display:grid;place-items:center;font-size:18px;font-weight:800;
 color:var(--acc);background:color-mix(in srgb,var(--acc) 14%,transparent);font-variant-numeric:tabular-nums}
.m169b{display:flex;gap:8px;margin-top:10px;flex-wrap:wrap}
.m169x summary{cursor:pointer;opacity:.7;font-weight:600;padding:6px 2px}
:root[data-theme="light"] .m169gr,:root[data-theme="light"] .m169n{color:#BF4706}
@media (prefers-color-scheme: light){:root:not([data-theme="dark"]) .m169gr,:root:not([data-theme="dark"]) .m169n{color:#BF4706}}
</style>`);
