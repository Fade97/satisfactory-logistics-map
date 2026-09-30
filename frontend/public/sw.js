// Service Worker der Logistikkarte.
//  - App-Hülle (index.html, JS/CSS mit Hash im Namen, Icons, Kartenbild): Cache zuerst, im Hintergrund erneuern
//  - /api/*: Netz zuerst; ohne Netz der letzte gespeicherte Stand (die Seite zeigt ihr Alter an)
//  - Schreibende Anfragen (POST) nie aus dem Cache
const SHELL = 'shell-v4', API = 'api-v2';
self.addEventListener('install', e => {
  e.waitUntil(caches.open(SHELL).then(c => c.addAll(['/', '/manifest.webmanifest', '/icon-192.png', '/icon.svg'])));
  self.skipWaiting();
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => ![SHELL, API].includes(k)).map(k => caches.delete(k)))));
  self.clients.claim();
});
self.addEventListener('fetch', e => {
  const u = new URL(e.request.url);
  if (e.request.method !== 'GET' || u.origin !== location.origin) return;
  if (u.pathname.startsWith('/api/')) {
    // Große, sich selten ändernde Daten und Verlauf nicht horten
    if (/\/api\/(frames|series|train-flow)/.test(u.pathname)) return;
    e.respondWith(fetch(e.request).then(r => {
      if (r.ok) { const c = r.clone(); caches.open(API).then(x => x.put(u.pathname, c)); }
      return r;
    }).catch(async () => {
      // Aus dem Cache, aber gekennzeichnet — die Seite zeigt dann „offline · letzter Stand“
      const r = await caches.open(API).then(x => x.match(u.pathname));
      if (!r) return new Response('{"error":"offline"}', { status: 503, headers: { 'Content-Type': 'application/json' } });
      const h = new Headers(r.headers); h.set('X-From-Cache', '1'); h.delete('ETag');
      return new Response(await r.blob(), { status: 200, headers: h });
    }));
    return;
  }
  // Navigation (index.html): Netz zuerst — sonst zeigt eine installierte App nach jedem Deploy eine alte Seite,
  // die auf nicht mehr vorhandene Bausteine verweist. Offline: gespeicherte Seite.
  if (e.request.mode === 'navigate') {
    e.respondWith(fetch(e.request).then(r => { if (r.ok) caches.open(SHELL).then(c => c.put('/', r.clone())); return r; })
      .catch(() => caches.open(SHELL).then(c => c.match('/'))));
    return;
  }
  // JS/CSS/Bilder: Dateien mit Hash im Namen ändern sich nie → Cache zuerst
  e.respondWith(caches.open(SHELL).then(async c => {
    const hit = await c.match(e.request);
    if (hit) return hit;
    const r = await fetch(e.request);
    if (r.ok && (r.headers.get('Content-Type') || '').indexOf('text/html') < 0) c.put(e.request, r.clone());
    return r;
  }));
});
