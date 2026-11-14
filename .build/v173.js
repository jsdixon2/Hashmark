/* ===== v173 (owner: "Label with backup to X", after x25). Player card for an RB listed #2 on Sleeper's depth chart: a
   "Backup to <starter>" panel near the top with the x25 measurements (2021-25, PPR): when the lead back missed a game a
   clear backup (1.5x the #3's production) averaged 11.8 pts, 12+ in 44% of those games (7.6 / 22% when he played);
   crowded backfields 7.1 vs 4.1. Lead backs miss 3+ of the remaining games about 1 in 4 times; age and injury history
   barely move it (x25). If the starter is listed Out/Doubtful/IR now, the line says so. No value change (x25: not
   supported). ===== */
function bk173(p){try{if(!p||p.pos!=="RB"||p.dc!==2||!p.team||p.team==="FA")return null;
  const mates=Object.values(PL).filter(q=>q&&q.pos==="RB"&&q.team===p.team&&q.id!==p.id);
  const st=mates.filter(q=>q.dc===1).sort((a,b)=>(rosPPG(b)||0)-(rosPPG(a)||0))[0];if(!st)return null;
  const r3=mates.filter(q=>q.dc===3).sort((a,b)=>(rosPPG(b)||0)-(rosPPG(a)||0))[0];const me=rosPPG(p)||0,th=r3?(rosPPG(r3)||0):0;
  return {st,clear:!r3||me>=1.5*th};}catch(e){return null;}}
function bk173Html(p){const b=bk173(p);if(!b)return "";const s=b.st,last=s.name.split(" ").slice(-1)[0],out=s.inj&&/^(Out|Doubtful|IR|PUP|NFI|Sus)/i.test(s.inj);
  const now=out?`<p class="bk173n"><b>${esc(s.name)} is listed ${esc(s.inj.split(" ")[0])}</b>: ${esc(p.name.split(" ").slice(-1)[0])} is next in line.</p>`:"";
  const stat=b.clear?`When a lead back misses a game, a clear backup like this has averaged <b>11.8 PPR points</b> (12+ in 44% of those games), vs 7.6 when the starter plays.`
    :`This backfield is crowded: when the lead back misses a game, backups like this have averaged <b>7.1 PPR points</b> (vs 4.1 when he plays).`;
  return `<section class="pan bk173"><div class="row sp"><h2>Backup to <button class="flnk" data-go="player-${s.id}">${esc(s.name)}</button></h2><span class="tag">${b.clear?"Clear #2":"Shared #2"}</span></div>${now}
    <p class="sub">${stat} Lead backs miss 3+ of their remaining games about 1 time in 4, and age or injury history barely changes that${s.age>=28?`, so ${esc(last)}'s age (${Math.floor(s.age)}) isn't a reason to pay extra`:""}. Tested on 2021-25 games.</p></section>`;}
vPlayer=(function(prev){return function(id){const h=prev(id);try{const x=bk173Html(PL[id]);if(!x)return h;const t=document.createElement("div");t.innerHTML=h;const f=t.firstElementChild;
  if(f)f.insertAdjacentHTML("afterend",x);else return x+h;return t.innerHTML;}catch(e){console.error(e);return h;}};})(vPlayer);
document.head.insertAdjacentHTML("beforeend",`<style>.bk173 h2 .flnk{font:inherit;color:inherit;text-transform:none}.bk173n{margin:8px 0 4px}</style>`);
