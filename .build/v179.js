/* ===== v179 (owner: every starter had played, yet the matchup said "Proj 191.1" for 178.2 live points and "8 of 8
   starters finished · 154.2 pts scored"):
   1. Live projections took each player's points as the MAX across all your leagues (livePtsMap), so a player who scores
      more under another league's settings inflated this league's live projection. The league being viewed (S.L, also
      set by withLeague) now uses its own matchup points; other players fall back to the cross-league map.
   2. The league scoring adjustment (lgCal) fades with the share of starters still to play, but "finished" only counted
      the schedule file's final flag; ESPN's final (gameState "post") now counts too, so it reaches 0 when games end.
   3. "N of M starters finished" counted only player slots; kicker and D/ST starters are now counted with their points,
      so the total matches the live score once everything is final. ===== */
livePtsMap=(function(prev){return function(){const m=prev();try{const L=S.L;if(!L||!L.matchups||!L.matchups.length)return m;
  const k=(L.id||"")+"|"+(L._mut||0)+"|"+m.size;if(S._lpm179&&S._lpm179.k===k&&S._lpm179.base===m)return S._lpm179.m;
  const out=new Map(m);for(const x of L.matchups.flat())for(const [id,v] of Object.entries((x&&x.pp)||{}))if(v!=null)out.set(id,+v||0);
  S._lpm179={k,base:m,m:out};return out;}catch(e){return m;}};})(livePtsMap);
teamWeek=(function(prev){return function(L,ti,ls){const r=prev(L,ti,ls);try{if(!r||!r.cal)return r;const rows=(r.rows||[]).filter(x=>x.p);if(!rows.length)return r;
  const done=x=>{const g=gameOf(x.p)||{};if(g.final)return true;try{const gs=gameState(x.p.team);return !!(gs&&gs.st==="post");}catch(e){return false;}};
  const left=rows.filter(x=>!done(x)).length/rows.length,full=lgCal(L),cal=full*left;r.proj+=cal-r.cal;r.cal=cal;}catch(e){}return r;};})(teamWeek);
alertsFor=(function(prev){return function(W){const a=prev(W);try{const ls=W&&W.ls;if(!ls||!ls.starters||!ls.pp)return a;
  const L=(S.leagues||[]).find(x=>x.teams&&x.teams.includes(W.t));if(!L||!L.allSlots)return a;
  let n=0,d=0,pts=0;L.allSlots.forEach((s,k)=>{if(!KDEF[s])return;const id=ls.starters[k];if(!id||id==="0")return;n++;const t=kdTeam(id);let fin=false;
    try{const g=t?gameOf({team:t}):null,gs=t?gameState(t):null;fin=!!((g&&g.final)||(gs&&gs.st==="post"));}catch(e){}
    if(fin){d++;pts+=+ls.pp[id]||0;}});
  if(!n)return a;const i=a.findIndex(x=>x.lvl==="info"&&/^\d+ of \d+ starters finished$/.test(x.msg));
  if(i>=0){const m=/^(\d+) of (\d+)/.exec(a[i].msg),p=/^(-?[\d.]+) pts scored/.exec(a[i].fix||"");
    a[i]={...a[i],msg:`${+m[1]+d} of ${+m[2]+n} starters finished`,fix:`${f1((p?+p[1]:0)+pts)} pts scored`};}
  return a;}catch(e){return a;}};})(alertsFor);
