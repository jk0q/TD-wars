// Service worker minimal : rend l'app installable (PWA) et met en cache
// la coquille statique. Le jeu lui-même nécessite le serveur (Socket.IO).
const CACHE = 'tdwars-v1';
const ASSETS = [
  '/', '/style.css', '/manifest.webmanifest',
  '/js/main.js', '/js/render.js', '/shared/data.js',
  '/icons/icon-192.png', '/icons/icon-512.png',
];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)));
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
  );
  self.clients.claim();
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  // jamais de cache pour socket.io (websocket/polling temps réel)
  if (url.pathname.startsWith('/socket.io/')) return;
  // réseau d'abord, cache en secours : on a toujours la dernière version
  // quand le serveur répond, et une coquille hors-ligne sinon
  e.respondWith(
    fetch(e.request)
      .then((res) => {
        if (res.ok && e.request.method === 'GET') {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(e.request, copy));
        }
        return res;
      })
      .catch(() => caches.match(e.request))
  );
});
