// Service Worker：让"今天吃什么"在断网时也能打开
const CACHE = "jtcsm-v1";
const ASSETS = [
  "./",
  "./index.html",
  "./manifest.json",
  "./icons/icon-192.png",
  "./icons/icon-512.png"
];

// 安装：把要用到的文件都缓存起来
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE)
      .then((cache) => cache.addAll(ASSETS))
      .then(() => self.skipWaiting())
  );
});

// 激活：清掉旧版本缓存
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// 请求：优先用缓存，没有再去网络取并顺手缓存
self.addEventListener("fetch", (event) => {
  event.respondWith(
    caches.match(event.request).then((hit) => {
      if (hit) return hit;
      return fetch(event.request)
        .then((res) => {
          const copy = res.clone();
          if (res.ok && event.request.method === "GET") {
            caches.open(CACHE).then((cache) => cache.put(event.request, copy));
          }
          return res;
        })
        .catch(() => {
          // 断网时打开页面，退回首页缓存
          if (event.request.mode === "navigate") return caches.match("./index.html");
          return new Response("", { status: 503, statusText: "Offline" });
        });
    })
  );
});
