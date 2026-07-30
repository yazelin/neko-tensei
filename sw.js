/* 轉生成貓貓的我們 — service worker
   兩層快取(做法沿用 token-unlimited / gewu 的實測筆記):
     SHELL —— 殼:HTML/CSS/manifest/小 icon。每次部署都 bump。
     ASSET —— 漫畫頁與角色圖。只有同名檔換內容才 bump。
   HTML network-first、資產 cache-first;match 一律 ignoreSearch+ignoreVary
   (GitHub Pages 回 Vary: Accept-Encoding,不加 ignoreVary 會 miss)。 */

const SHELL = 'nt-shell-v3';
const ASSET = 'nt-asset-v3';

const SHELL_FILES = [
  './', './index.html', './ep1.html',
  './char-xiaoniao.html', './char-xiaobai.html', './char-uncle.html', './char-leo.html',
  './style.css', './manifest.json',
  './icon-192.png', './icon-180.png', './favicon-32.png'
];

/* 背景暖快取,順序=閱讀順序:第一話 8 頁 → 角色圖 → 分享用資產。 */
const WARM = [
  './images/00-cover.webp', './images/01.webp', './images/02.webp', './images/03.webp',
  './images/04.webp', './images/05.webp', './images/06.webp', './images/07.webp',
  './images/char-xiaoniao.webp', './images/char-xiaobai.webp',
  './images/char-uncle.webp', './images/char-leo.webp',
  './icon-512.png', './og.jpg'
];

self.addEventListener('install', e => {
  self.skipWaiting();
  e.waitUntil(caches.open(SHELL).then(c =>
    Promise.allSettled(SHELL_FILES.map(f => c.add(f)))));
});

self.addEventListener('activate', e => {
  e.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(k => k !== SHELL && k !== ASSET).map(k => caches.delete(k)));
    await self.clients.claim();
    warm();   // 不 await:暖快取不擋接管
  })());
});

async function warm() {
  const c = await caches.open(ASSET);
  for (const url of WARM) {
    try {
      if (await c.match(url, { ignoreSearch: true, ignoreVary: true })) continue;
      const r = await fetch(url, { cache: 'reload' });
      if (r.ok) await c.put(url, r);
    } catch (_) { /* 斷線就停在這裡,下次啟動接著抓 */ }
  }
}

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  if (new URL(req.url).origin !== location.origin) return;

  const isHTML = req.mode === 'navigate' || (req.headers.get('accept') || '').includes('text/html');

  if (isHTML) {
    e.respondWith((async () => {
      try {
        const r = await fetch(req);
        const cp = r.clone();
        caches.open(SHELL).then(c => c.put(req, cp)).catch(() => {});
        return r;
      } catch (_) {
        const m = await caches.match(req, { ignoreSearch: true, ignoreVary: true });
        return m || await caches.match('./index.html', { ignoreVary: true }) || Response.error();
      }
    })());
  } else {
    e.respondWith((async () => {
      const m = await caches.match(req, { ignoreSearch: true, ignoreVary: true });
      if (m) return m;
      const r = await fetch(req);
      const cp = r.clone();
      caches.open(ASSET).then(c => c.put(req, cp)).catch(() => {});
      return r;
    })());
  }
});
