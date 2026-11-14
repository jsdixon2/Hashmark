/* ===== v174 (owner: "check for other discrepancies"; audit 2026-11-14). Playoff odds showed 56% on the Team hub and 60% on
   League standings / Roster for the same team: oddsFor caches simLeague (1,500 random seasons) on L._odds, and league
   rebuilds (withLeague) clear the cache, so each page could get a fresh random draw (+-2-3 pts of noise). simLeague now
   runs on a seeded generator (league id + week + every team's roster), so the same inputs always give the same odds.
   simTitle already had a fixed seed. Also p174: League rules hides empty Lineup / Settings boxes; Wire waiver stories drop
   "Started since 0 of 0 weeks"; v174 removes a dangling "·" on Buy low cards with no team note. ===== */
function sd174(str){let h=2166136261;for(let i=0;i<str.length;i++){h^=str.charCodeAt(i);h=Math.imul(h,16777619);}return h>>>0;}
function rng174(seed){let a=seed||1;return function(){a|=0;a=a+0x6D2B79F5|0;let t=Math.imul(a^a>>>15,1|a);t=t+Math.imul(t^t>>>7,61|t)^t;return ((t^t>>>14)>>>0)/4294967296;};}
simLeague=(function(prev){return function(L){const a=arguments,R=Math.random;
  const key=(L&&L.id)+"|"+S.week+"|"+(L&&L.teams?L.teams.map(t=>t.players.length+":"+(t.w||0)+"-"+(t.l||0)).join(","):"");Math.random=rng174(sd174(key));
  try{return prev.apply(this,a);}finally{Math.random=R;}};})(simLeague);
/* Buy-low / sell-high cards: the old one-line "Offer" (pre-v86, not checked for realism) sat next to the vetted Trade
   options block and could contradict it ("Offer X" + "No realistic trade built around him right now"). The options block
   is the answer, so the old Offer line is dropped whenever it is shown. */
sigCard=(function(prev){return function(x,kind){let h=prev(x,kind);try{if(/class="topt|No realistic trade built around him/.test(h))h=h.replace(/<div class="pay"><span class="eyebrow">Offer<\/span>[\s\S]*?<\/div>/,"");}catch(e){}return h;};})(sigCard);
