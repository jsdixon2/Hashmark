/* ===== v170 (owner: Players tab showed "No players match" in every league; filters hard to use).
   Bug: the player card's own tabs (Overview/Trends/Advanced/News...) use data-ptab too; the global click handler also set
   S.ptab from them, so after opening a player's Trends tab the Players list filtered on position "tr" (p170 stops that;
   allPlayers treats any unknown position as All).
   Filters reworked: search on its own row; position chips All/QB/RB/WR/TE; two dropdowns "Show" (everyone / available /
   yours / other teams) and "Sort" (value, this week, rest of season, season points, per game, breakout, safest,
   youngest); a count line; each row shows team · age · per game and the sorted number. ===== */
const PL170S=[["val","Value","market value",p=>-(p.val||0),p=>f0(p.val)],
  ["wk","This week","proj this week",p=>-(wkProj(p)||0),p=>f1(wkProj(p))],
  ["ros","Rest of season","per game ROS",p=>-(rosPPG(p)||0),p=>f1(rosPPG(p))],
  ["pts","Season points","season pts",p=>-(p.pts??-1),p=>p.pts==null?"–":f1(p.pts)],
  ["ppg","Per game","per game",p=>-(p.ppg??-1),p=>p.ppg==null?"–":f1(p.ppg)],
  ["brk","Breakout odds","breakout",p=>-(p.broke?-1:(p.brk??-1)),p=>p.broke?"Arrived":p.brk==null?"–":pc(p.brk)],
  ["risk","Safest","risk",p=>p.risk??999,p=>p.risk??"–"],
  ["age","Youngest","age",p=>p.age??99,p=>p.age??"–"]];
const PL170O=[["all","Everyone"],["avail","Available"],["mine","Yours"],["other","Other teams"]];
function pl170List(){const q=(S.pq||"").toLowerCase().trim(),own=S.plOwn||"all",pt=POSI.hasOwnProperty(S.ptab)?S.ptab:"ALL";
  let ps=Object.values(PL).filter(p=>POSI.hasOwnProperty(p.pos)&&(pt==="ALL"||p.pos===pt)&&(!q||p.name.toLowerCase().includes(q)||(p.team||"").toLowerCase()===q));
  if(own!=="all")ps=ps.filter(p=>ownerLbl(p).k===own);
  const s=PL170S.find(x=>x[0]===S.psort)||PL170S[0];let k=new Map();ps.forEach(p=>{let v;try{v=s[3](p);}catch(e){v=0;}k.set(p.id,isFinite(v)?v:0);});ps.sort((a,b)=>k.get(a.id)-k.get(b.id));
  return {ps,s,q};}
allPlayers=function(){const {ps,s,q}=pl170List();
  const row=p=>{const o=ownerLbl(p),bits=[p.team&&p.team!=="FA"?esc(p.team):"FA"];if(p.age)bits.push(p.age);if(s[0]!=="ppg"&&p.ppg!=null)bits.push(f1(p.ppg)+" ppg");let v="–";try{v=s[4](p);}catch(e){}
    return `<div class="pr" data-go="player-${p.id}" role="link" tabindex="0">${mono(p,1)}<div style="min-width:0"><div class="nm ell">${pos(p.pos)} ${esc(p.name)}</div><div class="meta ell">${p.inj?`<span class="warn">${esc(p.inj.split(" ")[0])}</span> · `:""}<span class="own ${o.k}">${esc(o.t)}</span> · ${bits.join(" · ")}</div></div><div style="text-align:right"><div class="num">${v}</div><div class="meta">${s[2]}</div></div></div>`;};
  return `<div class="pl170n sub">${ps.length.toLocaleString()} player${ps.length===1?"":"s"}${q?` matching “${esc(S.pq)}”`:""} · sorted by ${s[1].toLowerCase()}</div><div class="pan list">${lst(ps.slice(0,300).map(row),40,`No players match${q?` “${esc(S.pq)}”`:""}. <button class="btn ghost sm" data-pl170reset>Clear filters</button>`)}</div><p class="sub mt">Ownership is for ${esc(S.L?S.L.name:"this league")}. Values use this league’s format.</p>`;};
vWaivers=(function(prev){return function(){const t=S.plT||"wire";if(t!=="all")return prev();if(!POSI.hasOwnProperty(S.ptab))S.ptab="ALL";
  const sel=(id,lbl,opts,cur)=>`<label class="pl170s"><span>${lbl}</span><select data-pl170="${id}" aria-label="${lbl}">${opts.map(([k,n])=>`<option value="${k}"${k===cur?" selected":""}>${n}</option>`).join("")}</select></label>`;
  const ctl=`<div class="pgctl pl170"><div class="pl170t"><div class="seg sm"><button data-plt="wire">Waiver wire</button><button data-plt="all" class="on">All players</button></div>   <div class="field"><input id="pq" type="search" value="${esc(S.pq||"")}" placeholder="Name or team (DET)" aria-label="Search players" autocomplete="off"></div></div>
   <div class="seg sm pl170p">${["ALL","QB","RB","WR","TE"].map(x=>`<button data-ptab="${x}" class="${S.ptab===x?"on":""}">${x==="ALL"?"All":x}</button>`).join("")}</div>
   <div class="pl170r">${sel("own","Show",PL170O,S.plOwn||"all")}${sel("sort","Sort",PL170S.map(x=>[x[0],x[1]]),S.psort&&PL170S.some(x=>x[0]===S.psort)?S.psort:"val")}</div></div>`;
  return ctl+allPlayers();};})(vWaivers);
document.addEventListener("change",e=>{const s=e.target.closest("[data-pl170]");if(!s)return;if(s.dataset.pl170==="own")S.plOwn=s.value;else S.psort=s.value;render();},true);
document.addEventListener("click",e=>{if(e.target.closest("[data-pl170reset]")){e.stopPropagation();S.pq="";S.ptab="ALL";S.plOwn="all";render();}},true);
document.head.insertAdjacentHTML("beforeend",`<style>
.pl170t{display:flex;gap:8px;align-items:center}.pl170t .seg{flex:none}.pl170t .field{flex:1;min-width:0}
.pl170 .pl170p{display:grid!important;grid-template-columns:repeat(5,1fr);width:100%}.pl170 .pl170p button{text-align:center;justify-content:center}
.pl170r{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.pl170s{position:relative;display:flex;align-items:center;height:36px;border:1px solid var(--line);border-radius:999px;background:var(--panel2);padding:0 30px 0 12px;font-size:13px;min-width:0}
.pl170s span{opacity:.6;margin-right:6px;flex:none}
.pl170s select{appearance:none;-webkit-appearance:none;border:0;background:transparent;color:inherit;font:inherit;font-weight:600;min-width:0;flex:1;outline:none;padding:0}
.pl170s::after{content:"";position:absolute;right:13px;top:50%;width:6px;height:6px;border-right:1.6px solid currentColor;border-bottom:1.6px solid currentColor;transform:translateY(-70%) rotate(45deg);opacity:.6;pointer-events:none}
.pl170n{margin:2px 2px 8px}
</style>`);
