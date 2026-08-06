/* 轉生成貓貓的我們 — service worker
   兩層快取(做法沿用 token-unlimited / gewu 的實測筆記):
     SHELL —— 殼:HTML/CSS/manifest/小 icon。
     ASSET —— 漫畫頁與角色圖。
   兩層各自的版號是那層清單的內容 hash,由 build.py 算,不必也不要手動 bump。
   HTML network-first、資產 cache-first;match 一律 ignoreSearch+ignoreVary
   (GitHub Pages 回 Vary: Accept-Encoding,不加 ignoreVary 會 miss)。 */

/* 版號由 build.py 從清單裡每個檔案的內容算出來,別手改。改殼檔或換圖跑一次
   build.py 就會自己變;要強制所有讀者重來,改 build.py 的 EPOCH。 */
/* ver:start */
const SHELL = 'nt-shell-v20-6b4a8756';
const ASSET = 'nt-asset-v20-499435fb';
/* ver:end */

/* 以下兩份清單由 build.py 從 episodes.json 產生,別手改。 */
const SHELL_FILES = [
/* shell:start */
  './', './index.html',
  './ep/1.html', './ep/2.html', './ep/3.html', './ep/4.html', './ep/5.html',
  './char/xiaoniao.html', './char/xiaobai.html', './char/uncle.html', './char/leo.html', './char/kojiro.html',
  './style.css', './app.js', './manifest.json',
  './assets/icon-192.png', './assets/icon-180.png', './assets/favicon-32.png'/* shell:end */
];

/* 背景暖快取,順序=閱讀順序(第一話起) → 角色圖 → 分享用資產。 */
const WARM = [
/* warm:start */
  './images/ep1/00-cover.webp', './images/ep1/01.webp', './images/ep1/02.webp',
  './images/ep1/03.webp', './images/ep1/04.webp', './images/ep1/05.webp',
  './images/ep1/06.webp', './images/ep1/07.webp', './images/ep2/00-cover.webp',
  './images/ep2/01.webp', './images/ep2/02.webp', './images/ep2/03.webp',
  './images/ep2/04.webp', './images/ep2/05.webp', './images/ep2/06.webp',
  './images/ep3/00-cover.webp', './images/ep3/01.webp', './images/ep3/02.webp',
  './images/ep3/03.webp', './images/ep3/04.webp', './images/ep3/05.webp',
  './images/ep3/06.webp', './images/ep4/00-cover.webp', './images/ep4/01.webp',
  './images/ep4/02.webp', './images/ep4/03.webp', './images/ep4/04.webp',
  './images/ep4/05.webp', './images/ep4/06.webp', './images/ep5/00-cover.webp',
  './images/ep5/01.webp', './images/ep5/02.webp', './images/ep5/03.webp',
  './images/ep5/04.webp', './images/ep5/05.webp', './images/ep5/06.webp',
  './images/char-xiaoniao.webp', './images/char-xiaobai.webp', './images/char-uncle.webp',
  './images/char-leo.webp', './images/char-kojiro.webp', './assets/icon-512.png',
  './assets/og.jpg'/* warm:end */
];

/* 殼檔的絕對網址。查快取時要限定在 SHELL 裡找,不能用全域 caches.match()——
   那會搜遍所有快取,把執行期 ASSET 裡的舊 style.css / app.js 撈出來蓋掉新版。
   ASSET 不隨每次部署 bump(只有換圖才 bump),所以那種副本會活到天荒地老。 */
const SHELL_URLS = new Set(SHELL_FILES.map(f => new URL(f, self.registration.scope).href));
const bare = u => u.split('?')[0].split('#')[0];

self.addEventListener('install', e => {
  self.skipWaiting();
  e.waitUntil(caches.open(SHELL).then(c =>
    Promise.allSettled(SHELL_FILES.map(f => c.add(f)))));
});

self.addEventListener('activate', e => {
  e.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(k => k !== SHELL && k !== ASSET).map(k => caches.delete(k)));
    /* 一次性清理:舊版把 style.css / app.js 也寫進執行期 ASSET,而 ASSET 不隨
       部署 bump,那些過期副本會永遠蓋掉新版。把它們從 ASSET 挑掉。 */
    const a = await caches.open(ASSET);
    for (const r of await a.keys()) {
      if (SHELL_URLS.has(bare(r.url))) await a.delete(r);
    }
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
      // 殼檔只在 SHELL 裡找、也只寫回 SHELL;其餘才走執行期 ASSET。
      const name = SHELL_URLS.has(bare(req.url)) ? SHELL : ASSET;
      const c = await caches.open(name);
      const m = await c.match(req, { ignoreSearch: true, ignoreVary: true });
      if (m) return m;
      const r = await fetch(req);
      const cp = r.clone();
      c.put(req, cp).catch(() => {});
      return r;
    })());
  }
});
