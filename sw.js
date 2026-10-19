/* 캠퍼스타운 허브 — 안드로이드 설치용 서비스워커
 *
 * 방침: 화면(HTML·JS)은 "항상 서버 먼저".
 *   이 허브는 index.html 한 장에 전부 들어 있어서, 캐시가 이기면 옛 화면이 그대로 뜹니다.
 *   실제로 v125 때 10분 캐시 때문에 "버튼이 안 바뀐다"는 일이 있었습니다.
 *   그래서 HTML 은 네트워크를 먼저 쓰고, 네트워크가 끊겼을 때만 캐시를 꺼냅니다.
 *
 *   아이콘·설정 파일처럼 거의 안 바뀌는 것만 캐시를 먼저 씁니다.
 *
 * 로그인·회의 데이터는 여기서 손대지 않습니다 — Supabase 호출은 캐시하지 않습니다.
 */
const VERSION = "hub-v1";
const SHELL = [
  "./manifest.webmanifest",
  "./icon-192.png",
  "./icon-512.png",
  "./icon-512-maskable.png",
  "./apple-touch-icon.png",
];

self.addEventListener("install", (e) => {
  self.skipWaiting();                       // 새 버전이 곧바로 적용되게
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(SHELL)).catch(() => {}));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((ks) => Promise.all(ks.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);
  // 다른 서버(Supabase·구글·Jitsi)는 건드리지 않습니다
  if (url.origin !== self.location.origin) return;

  const isShell = SHELL.some((p) => url.pathname.endsWith(p.replace("./", "")));

  if (isShell) {
    // 아이콘·설정 — 캐시 먼저, 없으면 받아서 저장
    e.respondWith(
      caches.match(req).then((hit) =>
        hit || fetch(req).then((res) => {
          const copy = res.clone();
          caches.open(VERSION).then((c) => c.put(req, copy)).catch(() => {});
          return res;
        })
      )
    );
    return;
  }

  // 화면 — 항상 서버 먼저. 끊겼을 때만 캐시.
  e.respondWith(
    fetch(req)
      .then((res) => {
        if (res && res.ok && res.type === "basic") {
          const copy = res.clone();
          caches.open(VERSION).then((c) => c.put(req, copy)).catch(() => {});
        }
        return res;
      })
      .catch(() => caches.match(req).then((hit) => hit || caches.match("./index.html")))
  );
});
