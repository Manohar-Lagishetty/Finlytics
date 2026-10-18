// Finlytics service worker — required by Chrome for the "Add to Home screen"
// install prompt. Keeps it deliberately light: only caches static assets
// (css/js/icons/fonts), never HTML. Pages are server-rendered with CSRF
// tokens and session state, so caching them would serve stale forms/auth.
// Static assets are network-first (cache is only an offline fallback):
// filenames aren't content-hashed, so cache-first would keep serving old
// JS/CSS after a deploy. Bump CACHE to purge old caches on activate.
const CACHE = "finlytics-static-v2";

self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  const isStaticAsset = url.origin === self.location.origin && url.pathname.startsWith("/static/");
  if (!isStaticAsset) return; // let the browser handle everything else normally

  event.respondWith(
    caches.open(CACHE).then(async (cache) => {
      try {
        const response = await fetch(request);
        if (response.ok) cache.put(request, response.clone());
        return response;
      } catch (err) {
        const cached = await cache.match(request);
        if (cached) return cached;
        throw err;
      }
    })
  );
});
