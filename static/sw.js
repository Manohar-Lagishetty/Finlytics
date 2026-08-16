// Finlytics service worker — required by Chrome for the "Add to Home screen"
// install prompt. Keeps it deliberately light: only caches static assets
// (css/js/icons/fonts), never HTML. Pages are server-rendered with CSRF
// tokens and session state, so caching them would serve stale forms/auth.
const CACHE = "finlytics-static-v1";

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
      const cached = await cache.match(request);
      if (cached) return cached;
      const response = await fetch(request);
      if (response.ok) cache.put(request, response.clone());
      return response;
    })
  );
});
