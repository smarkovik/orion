const PREFIX = "__PREFIX__";
const CACHE = PREFIX + "-__VERSION__";
const MAX = 800;
const ROOT = new URL("./", self.location.href).pathname;

self.addEventListener("install", (e) => {
  const routes =
    e.addRoutes && typeof e.addRoutes === "function"
      ? e.addRoutes([{ condition: { urlPattern: { pathname: ROOT + "system/p.gif" } }, source: "network" }]).catch(() => {})
      : null;
  e.waitUntil(Promise.all([self.skipWaiting(), routes]));
});

self.addEventListener("activate", (e) =>
  e.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith(PREFIX + "-") && k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  )
);

async function store(request, response) {
  if (!response || !response.ok) return;
  const cache = await caches.open(CACHE);
  await cache.put(request, response);
  const keys = await cache.keys();
  await Promise.all(keys.slice(0, Math.max(0, keys.length - MAX)).map((k) => cache.delete(k)));
}

async function networkFirst(request) {
  try {
    const response = await fetch(request);
    store(request, response.clone()).catch(() => {});
    return response;
  } catch (err) {
    const cache = await caches.open(CACHE);
    const hit = (await cache.match(request)) || (await cache.match(request, { ignoreSearch: true }));
    if (hit) return hit;
    throw err;
  }
}

async function cacheFirst(request) {
  const cache = await caches.open(CACHE);
  const hit = await cache.match(request);
  if (hit) return hit;
  const response = await fetch(request);
  store(request, response.clone()).catch(() => {});
  return response;
}

self.addEventListener("fetch", (e) => {
  const request = e.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin || !url.pathname.startsWith(ROOT)) return;
  const path = url.pathname.slice(ROOT.length);
  if (path === "sw.js") return;
  if (/^(assets|thumbs)\//.test(path)) e.respondWith(cacheFirst(request));
  else if (request.mode === "navigate" || /(^|\/)[^/]*\.(html|xml|webmanifest)$/.test(path) || path === "") {
    e.respondWith(networkFirst(request));
  }
});

self.addEventListener("message", (e) => {
  const urls = (e.data && e.data.urls) || [];
  e.waitUntil(
    Promise.all(
      urls
        .filter((u) => typeof u === "string" && new URL(u, self.location.href).origin === self.location.origin)
        .filter((u) => !/\/sw\.js$/.test(u))
        .map((u) =>
          fetch(u)
            .then((r) => store(new Request(u), r))
            .catch(() => {})
        )
    )
  );
});
