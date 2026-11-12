const C="hashmark-v13",D="hashmark-data-v1",SHELL=["./","index.html","manifest.webmanifest","icon-192-p2.png","icon.svg"];
self.addEventListener("install",e=>{self.skipWaiting();e.waitUntil(caches.open(C).then(c=>c.addAll(SHELL)));});
self.addEventListener("activate",e=>e.waitUntil(caches.keys().then(k=>Promise.all(k.filter(x=>x!==C&&x!==D).map(x=>caches.delete(x)))).then(()=>self.clients.claim())));
/* data files: conditional requests. The worker keeps each file with its ETag / Last-Modified and asks the server
   "changed since?"; a 304 answer costs a few hundred bytes and the saved copy is used. Works offline too. */
async function dataFetch(req){const u=new URL(req.url),key=u.origin+u.pathname,c=await caches.open(D),cached=await c.match(key);
  const h=new Headers();if(cached){const et=cached.headers.get("ETag"),lm=cached.headers.get("Last-Modified");if(et)h.set("If-None-Match",et);else if(lm)h.set("If-Modified-Since",lm);}
  try{const r=await fetch(key,{headers:h,cache:"no-store"});if(r.status===304&&cached)return cached;if(r.ok){await c.put(key,r.clone());}return r;}
  catch(err){if(cached)return cached;throw err;}}
self.addEventListener("fetch",e=>{const u=new URL(e.request.url);if(u.origin!==location.origin||e.request.method!=="GET")return;
  if(/\/(data|bt\/idp)\/[^/]+\.json$/.test(u.pathname)){e.respondWith(dataFetch(e.request));return;}
  e.respondWith(fetch(e.request).then(r=>{const cp=r.clone();caches.open(C).then(c=>c.put(e.request,cp));return r;}).catch(()=>caches.match(e.request)));});
