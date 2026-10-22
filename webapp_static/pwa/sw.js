/* RAMON STORE - service worker (v2). Nunca guarda /api (saldo, compras, login). */
const V='rl-v2', SHELL=['/pwa/icon-192.png','/pwa/icon-512.png','/pwa/logo-96.png','/pwa/logo-256.png'];
self.addEventListener('install',e=>{e.waitUntil(caches.open(V).then(c=>c.addAll(SHELL)).then(()=>self.skipWaiting()))});
self.addEventListener('activate',e=>{e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k!==V).map(k=>caches.delete(k)))).then(()=>self.clients.claim()))});
const OFFLINE='<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>RAMON STORE</title><body style="margin:0;background:#000;color:#f4f4fa;font-family:sans-serif;display:flex;min-height:100vh;align-items:center;justify-content:center;text-align:center;padding:24px"><div><div style="font-size:48px">📡</div><h2>Sem conexão</h2><p style="color:#8d8da6">Conecte-se à internet para usar a RAMON STORE.</p><button onclick="location.reload()" style="background:#ffb020;border:0;border-radius:14px;padding:12px 22px;font-weight:700;font-size:16px">Tentar de novo</button></div>';
self.addEventListener('fetch',e=>{
  const r=e.request, u=new URL(r.url);
  if(r.method!=='GET'||u.origin!==location.origin||u.pathname.startsWith('/api/')||u.pathname.startsWith('/admin')) return;
  if(r.mode==='navigate'){
    e.respondWith(fetch(r).catch(()=>new Response(OFFLINE,{headers:{'Content-Type':'text/html; charset=utf-8'}})));
    return;
  }
  if(u.pathname.startsWith('/pwa/')||u.pathname==='/img'||u.pathname.startsWith('/avatar/')){
    e.respondWith(caches.match(r).then(h=>h||fetch(r).then(res=>{if(res.ok){const c=res.clone();caches.open(V).then(x=>x.put(r,c))}return res})));
  }
});
