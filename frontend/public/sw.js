// Ascend's offline helper. Keeps a copy of the app page so it opens instantly
// (and without data) on cheap phones, and shows a friendly screen with no signal.
// Job data always comes live from the server; it is never cached here.
const CACHE = "ascend-v1";
const SHELL = ["/", "/manifest.webmanifest", "/icon-192.png"];
const OFFLINE = `<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Ascend — offline</title>
<style>body{margin:0;font-family:system-ui,sans-serif;background:#EFF4EF;color:#10251A;display:flex;min-height:100vh;
align-items:center;justify-content:center;text-align:center;padding:24px}h1{font-size:22px}button{margin-top:16px;
padding:10px 18px;border:0;border-radius:8px;background:#0F2A1D;color:#E7F0EA;font-size:15px}</style></head>
<body><div><h1>You're offline</h1><p>Ascend needs a connection to load jobs.<br>Check your data or Wi-Fi and try again.</p>
<button onclick="location.reload()">Try again</button></div></body></html>`;

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET" || new URL(req.url).origin !== self.location.origin) return;  // API calls go straight to the server
  if (req.mode === "navigate") {
    // newest page when online (and keep it), last saved copy when not
    e.respondWith(fetch(req).then((res) => {
      const copy = res.clone(); caches.open(CACHE).then((c) => c.put("/", copy)); return res;
    }).catch(() => caches.match("/").then((r) => r || new Response(OFFLINE, { headers: { "Content-Type": "text/html; charset=utf-8" } }))));
    return;
  }
  e.respondWith(caches.match(req).then((r) => r || fetch(req)));
});
