// Service worker basico: cachea solo assets estaticos propios (imagenes de
// /static/images/, manifest.json) para que la app cargue mas rapido en wifi
// de resort lenta/inestable en visitas repetidas. A proposito NO cachea
// paginas HTML ni llamadas a la API: son server-rendered y dependen de
// sesion/usuario (login, achievements, videos subidos, etc.), cachearlas
// arriesgaria mostrar datos viejos. Esto es cacheo basico, no una
// estrategia de offline completo -- si no hay red y el asset no esta en
// cache, la carga simplemente falla como sin service worker.

const CACHE_NAME = "ski-app-static-v1";

// Precarga en el install los assets estaticos conocidos de antemano (fotos
// de hero/fondo e iconos de la PWA) para que la primera visita ya deje todo
// listo, ademas del cacheo "on demand" del fetch handler de mas abajo.
const PRECACHE_URLS = [
  "/static/manifest.json",
  "/static/images/bg-mountain.png",
  "/static/images/hero-mountain.jpg",
  "/static/images/hero-rotate-1.jpg",
  "/static/images/hero-rotate-2.jpg",
  "/static/images/hero-rotate-3.jpg",
  "/static/images/hero-rotate-4.jpg",
  "/static/images/icon-192.png",
  "/static/images/icon-512.png",
  "/static/images/apple-touch-icon.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);
  // Solo intercepta assets propios bajo /static/ -- nunca paginas (navigate)
  // ni endpoints de la API, para no arriesgar servir datos de usuario viejos.
  const isOwnStaticAsset = url.origin === self.location.origin && url.pathname.startsWith("/static/");
  if (!isOwnStaticAsset) return;

  // Cache-first: estos assets son fotos/iconos que no cambian en caliente,
  // asi que preferir el cache es seguro y evita esperar a la red.
  event.respondWith(
    caches.match(req).then((cached) => {
      if (cached) return cached;
      return fetch(req).then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(req, copy));
        }
        return res;
      });
    })
  );
});
