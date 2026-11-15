/* ===== v177 (owner "go"): Time Machine Draft, route `tm` (Scout tab + Scout hub tile). Data: data/tm.json from
   scripts/build_tm.py (nflverse weekly stats 1999-2025, split by team so traded players count for each team; college,
   draft year, Sleeper id). Loaded only when the game is opened.
   Rules: 7 rounds (QB, RB, RB, WR, WR, TE, FLEX); each roll = a random team-season (rolls are random every game); pick one
   player from that roster for an open slot (same player only once); 3 re-rolls. Score = each pick's PPR points per game
   that season (games floored at 6 so one big game can't carry a pick) + chemistry per pair: same team-season +2, else
   former teammates +1 (shared any team-season), else same franchise +1; plus same college +2 and same draft class +1;
   +1 for each pick who is on one of your Sleeper rosters. End: the lineup plays a 17-game season against 17 lineups
   drafted by a computer from random rolls (one of the top 2 available each round, no re-rolls); weekly scores vary 13%; record + chance
   each week; "best from your rolls" (local search over the 7 rolls you picked from) and the biggest miss; share image.
   Game in progress kept in localStorage hm_tm177 (per-device convenience). ===== */
const TM177={d:null,st:"idle",ts:null,fr:null};
const TM177_SLOTS=[["QB","QB"],["RB1","RB"],["RB2","RB"],["WR1","WR"],["WR2","WR"],["TE","TE"],["FLX","FLEX"]];
const TM177_NICK={ARI:"Cardinals",ATL:"Falcons",BAL:"Ravens",BUF:"Bills",CAR:"Panthers",CHI:"Bears",CIN:"Bengals",CLE:"Browns",DAL:"Cowboys",DEN:"Broncos",DET:"Lions",GB:"Packers",HOU:"Texans",IND:"Colts",JAX:"Jaguars",KC:"Chiefs",LA:"Rams",LAC:"Chargers",LV:"Raiders",MIA:"Dolphins",MIN:"Vikings",NE:"Patriots",NO:"Saints",NYG:"Giants",NYJ:"Jets",PHI:"Eagles",PIT:"Steelers",SEA:"Seahawks",SF:"49ers",TB:"Buccaneers",TEN:"Titans",WAS:"Washington"};
const TM177_CH={team:["same team-season",2,"#FF6B1A"],mates:["former teammates",1,"#4DA3FF"],fran:["same franchise",1,"#FF9AC8"],col:["same college",2,"#FFD23E"],draft:["same draft class",1,"#B98CFF"],mine:["on your roster",1,"#3DDBB4"]};
const TM177_MIN=6,TM177_SD=.13;
async function tm177Load(){if(TM177.d||TM177.st==="loading")return;TM177.st="loading";try{const r=await fetch("data/tm.json",{cache:"no-cache"});if(!r.ok)throw 0;TM177.d=await r.json();TM177.st="ready";
  const ts=new Map();for(const [k,rows] of Object.entries(TM177.d.T))for(const r of rows){if(!ts.has(r[0]))ts.set(r[0],new Set());ts.get(r[0]).add(k);}TM177.ts=ts;}catch(e){TM177.st="error";}if(route()==="tm")render();}
function tm177Row(k,i){const D=TM177.d,r=D.T[k]&&D.T[k][i];if(!r)return null;const P=D.P[r[0]],[tm,y]=k.split("|");const g=r[1];
  return {k,i,pi:r[0],name:P[0],pos:P[1],col:P[2],dy:P[3],sl:P[4],team:tm,year:+y,g,pts:r[2]/10,ppg:r[2]/10/Math.max(g,TM177_MIN),raw:r};}
function tm177Col(x){const c=(x.col||"").split(";").map(s=>s.trim()).filter(Boolean).join(" / ")||"No college listed";return c+(x.dy?` · '${String(x.dy).slice(2)} draft`:" · undrafted");}
function tm177Line(x){const r=x.raw,b=[];if(r[4]&&(x.pos==="QB"||r[4]>=10))b.push(`${r[3]}/${r[4]}, ${r[5].toLocaleString()} yds, ${r[6]} TD${r[7]?`, ${r[7]} INT`:""}`);if(r[8]&&(x.pos!=="QB"||r[9]>150))b.push(`${r[8]} car, ${r[9].toLocaleString()} yds${r[10]?`, ${r[10]} TD`:""}`);
  if(r[11])b.push(`${r[11]} rec, ${r[12].toLocaleString()} yds${r[13]?`, ${r[13]} TD`:""}`);return b.join(" · ")+` · ${x.g} g`;}
function tm177Mine(){if(TM177._mine&&TM177._mine.k===S.leagues.length)return TM177._mine.s;const s=new Set();try{for(const L of S.leagues||[]){const t=L.teams[mineIdx(L)];if(t)for(const id of t.players)s.add(String(id));}}catch(e){}TM177._mine={k:(S.leagues||[]).length,s};return s;}
function tm177Links(a,b){const out=[];if(a.k===b.k)out.push("team");else{const A=TM177.ts.get(a.pi),B=TM177.ts.get(b.pi);let m=false;if(A&&B)for(const k of A)if(B.has(k)){m=true;break;}if(m)out.push("mates");else if(a.team===b.team)out.push("fran");}
  const ca=(a.col||"").split(";").map(s=>s.trim()).filter(Boolean),cb=(b.col||"").split(";").map(s=>s.trim()).filter(Boolean);if(ca.some(c=>cb.includes(c)))out.push("col");
  if(a.dy&&a.dy===b.dy)out.push("draft");return out;}
function tm177Chem(picks){const mine=tm177Mine(),L=[];for(let i=0;i<picks.length;i++){const a=picks[i];if(a.sl&&mine.has(a.sl))L.push({t:"mine",a});for(let j=i+1;j<picks.length;j++)for(const t of tm177Links(a,picks[j]))L.push({t,a,b:picks[j]});}
  return {links:L,pts:L.reduce((s,x)=>s+TM177_CH[x.t][1],0)};}
function tm177Fit(pos,slots){const o=[];if(pos==="QB"){if(!slots.QB)o.push("QB");}else{for(const s of pos==="RB"?["RB1","RB2"]:pos==="WR"?["WR1","WR2"]:["TE"])if(!slots[s])o.push(s);if(!slots.FLX)o.push("FLX");}return o[0]||null;}
function tm177Rng(seed){let a=seed>>>0||1;return function(){a|=0;a=a+0x6D2B79F5|0;let t=Math.imul(a^a>>>15,1|a);t=t+Math.imul(t^t>>>7,61|t)^t;return ((t^t>>>14)>>>0)/4294967296;};}
function tm177Keys(){return TM177._keys||(TM177._keys=Object.keys(TM177.d.T));}
function tm177Picks(G){return TM177_SLOTS.map(([s])=>G.slots[s]).filter(Boolean).map(x=>tm177Row(x.k,x.i));}
function tm177New(){const seed=(Date.now()^(Math.random()*1e9))>>>0;S.tm={seed,slots:{},rolls:[],rerolls:3,cur:null,done:false,res:null};tm177Save();}
function tm177Save(){try{localStorage.setItem("hm_tm177",JSON.stringify(S.tm));}catch(e){}}
function tm177Restore(){if(S.tm)return;try{const v=JSON.parse(localStorage.getItem("hm_tm177")||"null");if(v&&v.slots)S.tm=v;}catch(e){}}
function tm177Roll(G,isRe){const keys=tm177Keys(),R=Math.random;let k=null;for(let t=0;t<200;t++){const c=keys[Math.floor(R()*keys.length)];if(G.rolls.includes(c)&&t<150)continue;
    const used=new Set(tm177Picks(G).map(p=>p.pi));if(TM177.d.T[c].some((r,i)=>{const x=tm177Row(c,i);return !used.has(x.pi)&&tm177Fit(x.pos,G.slots);})){k=c;break;}}
  if(isRe)G.rerolls--;G.cur=k;G.rolls.push(k);tm177Save();}
/* computer lineups for the season */
function tm177AI(rng){const keys=tm177Keys(),slots={},picks=[];let guard=0;while(picks.length<7&&guard++<60){const k=keys[Math.floor(rng()*keys.length)];const used=new Set(picks.map(p=>p.pi));
    const cs=TM177.d.T[k].map((r,i)=>tm177Row(k,i)).filter(x=>!used.has(x.pi)&&tm177Fit(x.pos,slots)).sort((a,b)=>b.ppg-a.ppg).slice(0,2);if(!cs.length)continue;const c=cs[Math.floor(rng()*cs.length)];slots[tm177Fit(c.pos,slots)]=1;picks.push(c);}
  const ch=tm177Chem(picks.map(p=>Object.assign({},p,{sl:""})));return picks.reduce((s,p)=>s+p.ppg,0)+ch.pts;}
function tm177Phi(z){return 1/(1+Math.exp(-1.702*z));}
function tm177Season(total,seed){const rng=tm177Rng(seed),opp=[];for(let i=0;i<17;i++)opp.push(tm177AI(rng));let w=0,wc=0;const g=()=>{let u=0,v=0;while(!u)u=rng();v=rng();return Math.sqrt(-2*Math.log(u))*Math.cos(2*Math.PI*v);};
  const games=opp.map(o=>{const p=tm177Phi((total-o)/Math.sqrt((TM177_SD*total)**2+(TM177_SD*o)**2));wc+=p;const me=total*(1+TM177_SD*g()),them=o*(1+TM177_SD*g());const won=me>them;if(won)w++;return {o,me,them,won};});
  return {w,l:17-games.filter(x=>x.won).length,wc:wc/17,games,opp};}
/* best lineup from the rolls you picked from */
function tm177Feasible(ps){const c={QB:0,RB:0,WR:0,TE:0};for(const p of ps)c[p.pos]++;if(new Set(ps.map(p=>p.pi)).size!==ps.length)return false;return c.QB===1&&c.RB>=2&&c.WR>=2&&c.TE>=1&&(c.RB-2)+(c.WR-2)+(c.TE-1)===1;}
function tm177Score(ps){return ps.reduce((s,p)=>s+p.ppg,0)+tm177Chem(ps).pts;}
function tm177Best(G){const keys=tm177Picks(G).map(p=>p.k);const C=keys.map(k=>TM177.d.T[k].map((r,i)=>tm177Row(k,i)).sort((a,b)=>b.ppg-a.ppg).slice(0,18));
  let cur=tm177Picks(G).slice(),best=tm177Score(cur);
  for(let pass=0;pass<6;pass++){let imp=false;for(let i=0;i<C.length;i++)for(const c of C[i]){const t=cur.slice();t[i]=c;if(!tm177Feasible(t))continue;const s=tm177Score(t);if(s>best+1e-9){best=s;cur=t;imp=true;}}
    for(let i=0;i<C.length&&!imp;i++)for(let j=i+1;j<C.length;j++)for(const a of C[i].slice(0,8))for(const b of C[j].slice(0,8)){const t=cur.slice();t[i]=a;t[j]=b;if(!tm177Feasible(t))continue;const s=tm177Score(t);if(s>best+1e-9){best=s;cur=t;imp=true;}}
    if(!imp)break;}
  return {picks:cur,total:best};}
function tm177Finish(G){const ps=tm177Picks(G),ch=tm177Chem(ps),tot=ps.reduce((s,p)=>s+p.ppg,0)+ch.pts,sea=tm177Season(tot,G.seed),B=tm177Best(G),bs=tm177Season(B.total,G.seed);
  const mine=tm177Picks(G);let miss=null;B.picks.forEach((p,i)=>{const m=mine[i];if(m&&p.pi!==m.pi){const d=p.ppg-m.ppg;if(!miss||d>miss.d)miss={d,from:m,to:p};}});
  G.res={tot,chem:ch.pts,w:sea.w,l:17-sea.w,wc:sea.wc,bt:B.total,bw:bs.w,best:B.picks.map(p=>[p.k,p.i]),miss:miss?{d:miss.d,from:[miss.from.k,miss.from.i],to:[miss.to.k,miss.to.i]}:null};G.done=true;
  try{const H=JSON.parse(localStorage.getItem("hm_tm177h")||"[]");H.unshift({w:sea.w,t:Math.round(tot*10)/10,at:Date.now()});localStorage.setItem("hm_tm177h",JSON.stringify(H.slice(0,50)));}catch(e){}tm177Save();}
/* ---- view ---- */
const TM177_POS={WR1:[24,16],TE:[136,16],WR2:[248,16],RB1:[24,138],FLX:[136,138],RB2:[248,138],QB:[136,258]};
function tm177Tile(s,lab,x){const [l,t]=TM177_POS[s];if(!x)return `<div class="tm177s" style="left:${l}px;top:${t}px">${lab}</div>`;const mine=x.sl&&tm177Mine().has(x.sl);
  return `<div class="tm177t${mine?" mine":""}" style="left:${l}px;top:${t}px"><span class="ps">${lab}</span>${mine?'<span class="yo">YOURS</span>':""}<div class="tb">${tbadge(x.team,"sm")}</div><div class="n">${esc(x.name)}</div><div class="y">${x.year}</div><div class="c">${esc(((x.col||"").split(";")[0]||"").trim())}</div><div class="f num">${f1(x.ppg)}</div></div>`;}
function tm177Board(G){const ps={};for(const [s] of TM177_SLOTS){const v=G.slots[s];if(v)ps[s]=tm177Row(v.k,v.i);}const arr=Object.entries(ps);const C=s=>{const [l,t]=TM177_POS[s];return [l+43,t+52];};
  let lines="";const seen={};for(let i=0;i<arr.length;i++)for(let j=i+1;j<arr.length;j++){const ls=tm177Links(arr[i][1],arr[j][1]);ls.forEach((t,n)=>{const [x1,y1]=C(arr[i][0]),[x2,y2]=C(arr[j][0]);const off=(n-(ls.length-1)/2)*5;
    lines+=`<line x1="${x1+off}" y1="${y1+off}" x2="${x2+off}" y2="${y2+off}" stroke="${TM177_CH[t][2]}" stroke-width="3" stroke-linecap="round"${t==="mates"||t==="fran"?' stroke-dasharray="6 5"':""} opacity=".9"/>`;});}
  return `<div class="tm177b"><svg viewBox="0 0 358 370">${lines}</svg>${TM177_SLOTS.map(([s,lab])=>tm177Tile(s,lab,ps[s])).join("")}</div>
   <div class="tm177leg">${Object.values(TM177_CH).map(([n,v,c])=>`<span style="--c:${c}">${n} +${v}</span>`).join("")}</div>`;}
function tm177Kpi(G){const ps=tm177Picks(G),ch=tm177Chem(ps),f=ps.reduce((s,p)=>s+p.ppg,0);return `<div class="tm177k"><div><b class="num">${f1(f)}</b><span>Player FPPG</span></div><div><b class="num o">+${ch.pts}</b><span>⚡ Chemistry</span></div><div><b class="num">${f1(f+ch.pts)}</b><span>Total</span></div></div>`;}
function tm177Sheet(G){const k=G.cur,[tm,y]=k.split("|"),ps=tm177Picks(G),used=new Set(ps.map(p=>p.pi)),F=S.tm177F||"all",mine=tm177Mine();
  const rows=TM177.d.T[k].map((r,i)=>tm177Row(k,i)).map(x=>{const slot=used.has(x.pi)?null:tm177Fit(x.pos,G.slots);const ls=[];for(const p of ps)for(const t of tm177Links(x,p))ls.push({t,p});if(x.sl&&mine.has(x.sl))ls.push({t:"mine"});
    return {x,slot,ls,add:ls.reduce((s,l)=>s+TM177_CH[l.t][1],0)};}).filter(o=>F==="all"||(F==="chem"?o.ls.length&&o.slot:o.x.pos===F)).sort((a,b)=>(!!b.slot-!!a.slot)||((b.x.ppg+b.add)-(a.x.ppg+a.add)));
  const chip=l=>`<span class="tm177c" style="--c:${TM177_CH[l.t][2]}">${l.t==="mine"?"on your roster":`${TM177_CH[l.t][0]}${l.p?" · "+esc(l.p.name.split(" ").slice(-1)[0]):""}`} +${TM177_CH[l.t][1]}</span>`;
  const row=o=>`<button class="tm177r${o.slot?"":" off"}"${o.slot?` data-tm177p="${o.x.i}"`:""}><span class="tm177pos">${o.x.pos}</span><span class="tm177rn"><b>${esc(o.x.name)}</b><span class="sub">${esc(tm177Line(o.x))}${o.slot?"":used.has(o.x.pi)?" · already picked":` · no open ${o.x.pos} slot`}</span><span class="tm177col">${esc(tm177Col(o.x))}</span></span><span class="tm177rf"><b class="num">${f1(o.x.ppg)}</b><small>PPR/g</small>${o.add&&o.slot?`<i>+${o.add}</i>`:""}</span></button>`;
  return `<section class="pan mt tm177sh"><div class="tm177sh1">${tbadge(tm)}<div><b>${y} ${TM177_NICK[tm]||tm}</b><div class="sub">${TM177.d.T[k].length} players · open: ${TM177_SLOTS.filter(([s])=>!G.slots[s]).map(x=>x[1]).join(", ")}</div></div></div>
   <div class="seg sm tm177f">${[["all","All"],["QB","QB"],["RB","RB"],["WR","WR"],["TE","TE"],["chem","Fits chemistry"]].map(([v,n])=>`<button data-tm177f="${v}" class="${F===v?"on":""}">${n}</button>`).join("")}</div>
   ${rows.map(row).join("")||`<p class="sub">No one here fits that filter.</p>`}
   ${G.rerolls>0?`<button class="btn ghost tm177wide" data-tm177re>Re-roll (${G.rerolls} left)</button>`:`<p class="sub mt">No re-rolls left: pick someone from this roster.</p>`}</section>`;}
function tm177Result(G){const R=G.res,ps=tm177Picks(G),ch=tm177Chem(ps),B=R.best.map(([k,i])=>tm177Row(k,i));
  const line=x=>`<div class="tm177rl"><span class="tm177pos">${x.pos}</span><span>${esc(x.name)} <span class="sub">${x.team} ${x.year}${x.sl&&tm177Mine().has(x.sl)?" · yours":""}</span></span><b class="num">${f1(x.ppg)}</b></div>`;
  const cl=l=>`<div class="tm177cr"><span>${l.t==="mine"?`${esc(l.a.name)} · on your roster`:`${esc(l.a.name.split(" ").slice(-1)[0])} + ${esc(l.b.name.split(" ").slice(-1)[0])} · ${TM177_CH[l.t][0]}${l.t==="draft"?` (${l.a.dy})`:l.t==="col"?` (${esc((l.a.col||"").split(";")[0])})`:""}`}</span><b>+${TM177_CH[l.t][1]}</b></div>`;
  const miss=R.miss?(()=>{const a=tm177Row(...R.miss.from),b=tm177Row(...R.miss.to);return `Biggest miss: ${esc(b.name)} (${b.team} ${b.year}) over ${esc(a.name)}, +${f1(b.ppg-a.ppg)} a week before chemistry.`;})():"You already built the best lineup these rolls allowed.";
  return `<section class="pan tm177res"><div class="sub">Your lineup played a 17-game season against computer-drafted lineups</div><div class="tm177rec">${R.w}<span>–</span>${17-R.w}</div>
   <div class="sub">${f1(R.tot)} a week (${f1(R.tot-R.chem)} players + ${R.chem} chemistry) · average win chance ${pc(R.wc)}${Math.abs(R.w-Math.round(R.wc*17))>=3?` · a typical season for this lineup is about ${Math.round(R.wc*17)}–${17-Math.round(R.wc*17)}, so ${R.w>Math.round(R.wc*17)?"the bounces went your way":"the bounces went against you"}`:""}</div><div class="bar"><i style="width:${PCT(R.wc)}%"></i></div></section>
   <section class="pan mt"><h2>Your lineup</h2>${ps.map(line).join("")}</section>
   <section class="pan mt"><div class="row sp"><h2>Chemistry</h2><span class="tag">+${ch.pts}</span></div>${ch.links.map(cl).join("")||`<p class="sub">No links this time.</p>`}</section>
   <section class="pan mt"><div class="row sp"><h2>Best from your rolls</h2><span class="tag">${R.bw}–${17-R.bw}</span></div><p class="sub">${f1(R.bt)} a week was possible from the same seven rosters. ${miss}</p>
    <details class="mt"><summary class="sub">Show that lineup</summary>${B.map(line).join("")}</details></section>
   <button class="btn tm177wide mt" data-tm177share>Share result</button><button class="btn ghost tm177wide" data-tm177new>Play again (new rolls)</button>`;}
function vTM(){tm177Restore();if(!TM177.d){if(TM177.st==="idle")setTimeout(tm177Load,0);return `<section class="pan"><p class="sub">${TM177.st==="error"?"The player history file isn't built yet. It appears after the build-tm GitHub Action runs.":"Loading 27 seasons of players…"}</p></section>`;}
  if(!S.tm)tm177New();const G=S.tm;const D=TM177.d;
  const intro=`<p class="sub">Roll a team and a season (${D.first}–${D.last}), pick one player from that roster, seven rounds. Then your lineup plays a 17-game season. <button class="inf" data-inf="tm177" aria-label="How Time Machine Draft works">i</button></p>`;
  if(G.done&&G.res)return intro+tm177Result(G);
  const n=Object.keys(G.slots).length;
  const head=`<div class="tm177h"><div class="tm177rd">Round <b>${Math.min(7,n+1)}</b>/7</div><span class="tag">${G.rerolls} re-roll${G.rerolls===1?"":"s"}</span><button class="btn ghost sm" data-tm177new>New game</button></div>`;
  const roll=G.cur?tm177Sheet(G):`<div class="tm177roll"><div><span>Team</span><b>?</b><em>any franchise</em></div><div><span>Season</span><b>?</b><em>${D.first}–${D.last}</em></div></div><button class="btn tm177wide tm177go" data-tm177roll>🎲 Roll</button>`;
  return intro+head+tm177Kpi(G)+tm177Board(G)+roll;}
DEFS.tm177=["Time Machine Draft","Each round rolls a random NFL team and season from "+"1999"+" on. Pick one player from that roster for an open slot (QB, two RB, two WR, TE, FLEX); the same player can only be picked once. You get three re-rolls a game.\n\nScore: each pick's PPR points per game that season (games count as at least 6, so one big game can't carry a pick), plus chemistry for each pair: same team and season +2; otherwise former teammates +1, otherwise same franchise +1; plus same college +2 and same draft class +1. Each pick on one of your Sleeper rosters adds +1.\n\nYour lineup then plays 17 games against lineups drafted by the computer from random rolls (each round it takes one of the two best available players, no re-rolls). Weekly scores swing about 13% either way. Stats: nflverse (CC-BY 4.0), split by team for traded players."];
document.addEventListener("click",e=>{const t=e.target.closest&&e.target.closest("[data-tm177roll],[data-tm177re],[data-tm177p],[data-tm177new],[data-tm177f],[data-tm177share]");if(!t||!S.tm&&!t.dataset.tm177new)return;e.stopPropagation();const G=S.tm;
  if(t.dataset.tm177roll!=null){tm177Roll(G,false);}
  else if(t.dataset.tm177re!=null){if(G.rerolls>0){G.rolls=G.rolls.filter(k=>k!==G.cur);tm177Roll(G,true);}}
  else if(t.dataset.tm177f){S.tm177F=t.dataset.tm177f;}
  else if(t.dataset.tm177new!=null){tm177New();}
  else if(t.dataset.tm177share!=null){tm177Share(G);return;}
  else if(t.dataset.tm177p!=null){const x=tm177Row(G.cur,+t.dataset.tm177p);const s=x&&tm177Fit(x.pos,G.slots);if(!s)return;G.slots[s]={k:G.cur,i:x.i};G.cur=null;S.tm177F="all";if(Object.keys(G.slots).length>=7)tm177Finish(G);tm177Save();window.scrollTo({top:0,behavior:"smooth"});}
  render();},true);
async function tm177Share(G){try{const R=G.res,ps=tm177Picks(G),W=1080,H=1350,c=document.createElement("canvas");c.width=W;c.height=H;const g=c.getContext("2d");try{await document.fonts.ready;}catch(e){}
  const F1='"Space Grotesk",system-ui,sans-serif',F2='Inter,system-ui,sans-serif';g.fillStyle="#0B0C0E";g.fillRect(0,0,W,H);const gr=g.createRadialGradient(0,0,0,0,0,900);gr.addColorStop(0,"rgba(255,107,26,.28)");gr.addColorStop(1,"rgba(255,107,26,0)");g.fillStyle=gr;g.fillRect(0,0,W,H);
  g.fillStyle="#F2F1EC";g.font=`700 40px ${F1}`;g.fillText("hashmark",70,110);g.fillStyle="#FF6B1A";g.font=`700 30px ${F2}`;g.fillText("TIME MACHINE DRAFT",70,170);
  g.fillStyle="#F2F1EC";g.font=`800 230px ${F1}`;g.fillText(`${R.w}–${17-R.w}`,62,400);g.fillStyle="#9BA1A9";g.font=`500 32px ${F2}`;g.fillText(`${f1(R.tot)} a week · ${R.chem} chemistry · best possible ${R.bw}–${17-R.bw}`,70,460);
  let y=560;for(const p of ps){g.fillStyle="#1E2126";g.beginPath();g.roundRect(70,y-52,940,78,18);g.fill();g.fillStyle="#9BA1A9";g.font=`700 26px ${F2}`;g.fillText(p.pos,100,y);g.fillStyle="#F2F1EC";g.font=`600 34px ${F2}`;g.fillText(p.name,190,y);
    g.fillStyle="#9BA1A9";g.font=`500 26px ${F2}`;g.fillText(`${p.team} ${p.year}`,190+g.measureText(p.name).width*1.0+26,y);g.fillStyle="#FF6B1A";g.font=`700 34px ${F1}`;g.textAlign="right";g.fillText(f1(p.ppg),980,y);g.textAlign="left";y+=96;}
  const blob=await new Promise(r=>c.toBlob(r,"image/png"));const file=new File([blob],"time-machine.png",{type:"image/png"});
  if(navigator.canShare&&navigator.canShare({files:[file]}))await navigator.share({files:[file],title:"Time Machine Draft"});else{const a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download="time-machine.png";a.click();}}catch(e){console.error(e);}}
vHome=(function(prev){return function(){if(route()==="tm")return `<div data-nolink>${vTM()}</div>`;return prev();};})(vHome);
pageTitle=(function(prev){return function(r){if(r==="tm")return {eb:["Scout"],h:"Time Machine Draft"};return prev(r);};})(pageTitle);
LABEL=(function(prev){return function(r){return r==="tm"?"Time Machine":prev(r);};})(LABEL);
tabOf=(function(prev){return function(r){return r==="tm"?"tm":prev(r);};})(tabOf);
try{if(!HUBS.scout.tabs.some(t=>t[0]==="tm"))HUBS.scout.tabs.push(["tm","Time Machine"]);}catch(e){}
vScoutLand=(function(prev){return function(){const h=prev();try{let H=[];try{H=JSON.parse(localStorage.getItem("hm_tm177h")||"[]");}catch(e){}const best=H.length?Math.max(...H.map(x=>x.w)):null;
  return `<button class="tm177land" data-go="tm"><span class="tm177li">🎲</span><span><b>Time Machine Draft</b><span class="sub">Roll a team and a season from 1999 on, draft seven players, play a 17-game season.${best!=null?` Your best: ${best}–${17-best}.`:""}</span></span>${CHEV}</button>`+h;}catch(e){return h;}};})(vScoutLand);
document.head.insertAdjacentHTML("beforeend",`<style>
.tm177h{display:flex;align-items:center;gap:8px;margin:10px 0}.tm177rd{font-weight:700;font-size:16px;margin-right:auto}.tm177rd b{color:var(--acc)}
.tm177k{display:grid;grid-template-columns:repeat(3,1fr);background:var(--panel);border-radius:18px;padding:12px 6px;text-align:center}.tm177k b{display:block;font-size:22px;font-weight:800}.tm177k b.o{color:var(--acc)}.tm177k span{font-size:10.5px;font-weight:600;letter-spacing:.07em;color:var(--muted);text-transform:uppercase}
.tm177b{position:relative;margin:12px auto 0;width:358px;max-width:100%;height:370px;border-radius:22px;background:radial-gradient(120% 90% at 50% 100%,color-mix(in srgb,#2E8B57 22%,var(--panel)),var(--panel) 70%);border:1px solid var(--line);overflow:hidden}
.tm177b svg{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}
.tm177s{position:absolute;width:86px;height:108px;border-radius:16px;border:1.5px dashed var(--line);display:grid;place-items:center;font-weight:700;font-size:13px;color:var(--muted);background:color-mix(in srgb,var(--bg) 35%,transparent)}
.tm177t{position:absolute;width:86px;min-height:108px;border-radius:16px;background:var(--panel2);border:1.5px solid var(--line);padding:9px 5px 6px;text-align:center}.tm177t.mine{border-color:#3DDBB4}
.tm177t .ps{position:absolute;top:-9px;left:7px;font-size:9px;font-weight:800;background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:2px 5px;color:var(--muted)}
.tm177t .yo{position:absolute;top:-9px;right:6px;font-size:9px;font-weight:800;background:#3DDBB4;color:#053;border-radius:6px;padding:2px 5px}
.tm177t .tb{margin-bottom:4px}.tm177t .n{font-size:11.5px;font-weight:700;line-height:1.15;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}.tm177t .y{font-size:10px;color:var(--muted)}.tm177t .c{font-size:9.5px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.tm177col{font-size:11.5px;color:var(--ink);opacity:.8;margin-top:2px}.tm177t .f{font-weight:800;font-size:13px;color:var(--acc)}
.tm177leg{display:flex;flex-wrap:wrap;gap:6px 12px;justify-content:center;margin-top:10px;font-size:11px;color:var(--muted)}.tm177leg span:before{content:"";display:inline-block;width:12px;height:3px;border-radius:2px;background:var(--c);margin-right:5px;vertical-align:middle}
.tm177roll{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px}.tm177roll div{background:var(--panel);border-radius:16px;padding:10px;text-align:center;display:flex;flex-direction:column}.tm177roll span{font-size:10.5px;font-weight:600;letter-spacing:.08em;color:var(--muted);text-transform:uppercase}.tm177roll b{font-size:22px}.tm177roll em{font-style:normal;font-size:12px;color:var(--muted)}
.tm177wide{display:block;width:100%;margin-top:10px}.tm177go{padding:14px;font-size:16px}
.tm177sh1{display:flex;align-items:center;gap:10px}.tm177sh1 b{font-size:18px}.tm177f{margin:12px 0 4px;flex-wrap:wrap}
.tm177r{display:grid;grid-template-columns:auto 1fr auto;gap:10px;align-items:center;width:100%;text-align:left;padding:10px 0;border:0;border-top:1px solid var(--line);border-radius:0;background:none;box-shadow:none;color:inherit;font:inherit}.tm177r.off{opacity:.42}
.tm177pos{font-size:10px;font-weight:700;background:var(--panel2);border-radius:6px;padding:4px 6px;color:var(--muted)}.tm177rn{display:flex;flex-direction:column;min-width:0}.tm177rn .sub{font-size:11.5px}
.tm177rf{text-align:right;display:flex;flex-direction:column;align-items:flex-end}.tm177rf b{font-size:16px}.tm177rf small{font-size:10px;color:var(--muted)}.tm177rf i{font-style:normal;font-weight:700;font-size:12px;color:var(--acc)}
.tm177c{display:inline-block;font-size:10px;font-weight:700;border-radius:6px;padding:1px 6px;margin:4px 4px 0 0;background:color-mix(in srgb,var(--c) 22%,transparent);color:var(--ink);box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--c) 55%,transparent)}
.tm177res{position:relative;overflow:hidden}.tm177res:before{content:"";position:absolute;inset:0;background:radial-gradient(120% 80% at 0% 0%,color-mix(in srgb,var(--acc) 22%,transparent),transparent 60%);pointer-events:none}
.tm177rec{position:relative;font-size:64px;font-weight:900;line-height:1;letter-spacing:-.03em;margin:6px 0}.tm177rec span{color:var(--acc)}
.tm177res .bar{position:relative;height:8px;border-radius:4px;background:var(--panel2);overflow:hidden;margin-top:10px}.tm177res .bar i{display:block;height:100%;background:linear-gradient(90deg,#FF6B1A,#FF9A57)}
.tm177rl{display:grid;grid-template-columns:auto 1fr auto;gap:8px;align-items:center;padding:7px 0;border-top:1px solid var(--line);font-size:13.5px}.tm177rl:first-of-type{border-top:0}
.tm177cr{display:flex;justify-content:space-between;gap:10px;font-size:13px;padding:6px 0;border-top:1px solid var(--line)}.tm177cr:first-of-type{border-top:0}.tm177cr b{color:var(--acc)}
.tm177land{display:flex;align-items:center;gap:12px;width:100%;text-align:left;background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:14px;margin-bottom:12px}.tm177land .tm177li{font-size:26px}.tm177land b{display:block;font-size:16px}.tm177land .sub{display:block;font-size:12.5px}
:root[data-theme="light"] .tm177k b.o,:root[data-theme="light"] .tm177t .f,:root[data-theme="light"] .tm177rf i,:root[data-theme="light"] .tm177cr b,:root[data-theme="light"] .tm177rd b{color:#BF4706}
@media (prefers-color-scheme: light){:root:not([data-theme="dark"]) .tm177k b.o,:root:not([data-theme="dark"]) .tm177t .f,:root:not([data-theme="dark"]) .tm177rf i,:root:not([data-theme="dark"]) .tm177cr b,:root:not([data-theme="dark"]) .tm177rd b{color:#BF4706}}
</style>`);
