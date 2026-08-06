// Service Worker：让"今天吃什么"在断网时也能打开
// 版本 v2：页面改为"网络优先"——联网时永远显示最新版，断网才用缓存
// 以后只改 index.html 的话，重新上传即可，无需动这里。
// 只有改了图标或 manifest.json 时，才需要把下面 CACHE 的版本号往上加（v3、v4…）。
const CACHE = "jtcsm-v2";
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

// 请求：
//   - 页面（HTML）：网络优先 → 联网时每次都是最新版，不再被旧缓存困住
//   - 其他资源（图标、清单）：缓存优先 → 固定文件直接用缓存更快
self.addEventListener("fetch", (event) => {
  // 页面导航：优先网络，断网才退回缓存
  if (event.request.mode === "navigate") {
    event.respondWith(
      fetch(event.request, { cache: "no-store" })   // 绕过浏览器 HTTP 缓存，确保拿到最新
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((cache) => cache.put(event.request, copy));
          return res;
        })
        .catch(() =>
          caches.match(event.request)
            .then((hit) => hit || caches.match("./index.html"))  // 断网时退回缓存的页面
        )
    );
    return;
  }

  // 其他请求：优先缓存，没有再去网络取并顺手缓存
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
          return new Response("", { status: 503, statusText: "Offline" });
        });
    })
  );
});
