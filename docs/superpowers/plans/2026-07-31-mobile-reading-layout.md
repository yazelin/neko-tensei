# 行動版閱讀體驗 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 讓 neko-tensei 在手機上像一個看漫畫的 app——閱讀頁沉浸式（頂欄自動隱現、底部進度條），首頁與角色頁有固定 tabbar 與「繼續閱讀」卡。

**Architecture:** 全站共用一支 `app.js`，靠頁面上有沒有 `main.reader` 分流成「閱讀模式」與「殼模式」。閱讀頁的固定頂欄與進度條由 `build.py` 產進 HTML（自成一頁、無 JS 也看得到），`app.js` 只負責行為。tabbar 與繼續閱讀卡由 `app.js` 注入，因為它們本來就需要 JS（量高度、讀 localStorage）。

**Tech Stack:** 純靜態站（HTML/CSS/vanilla JS）＋ Python 產生器（`build.py`）。驗收用全域安裝的 Playwright 跑 iPhone 13 尺寸。

## Global Constraints

- 設計來源：`docs/superpowers/specs/2026-07-31-mobile-reading-layout-design.md`
- localStorage key 一律 `nt-` 前綴。`yazelin.github.io` 是所有 Pages 專案共用的 origin，用通名會跟別的專案互相覆蓋
- 手機斷點固定用 `max-width:720px`，與現有 `.reader` 的 `max-width:720px` 一致
- 底部固定元素一律吃 `env(safe-area-inset-bottom)`
- `ep*.html` 是 `build.py` 的產生檔，**永遠不要手改**；要改就改 `build.py`
- 對外文字用正體中文與全形標點
- 每次改完 `build.py` 都要重跑 `python3 build.py`，並在最後一個任務 bump `sw.js` 的 `SHELL` / `ASSET`
- 驗收指令一律 `NODE_PATH=$(npm root -g) node scripts/verify-mobile.js`（全域 playwright@1.54.1，沒有 `package.json`，不要新增）

---

## File Structure

| 檔案 | 責任 |
|---|---|
| `app.js`（新增） | 全站行動版行為：進度讀寫、閱讀模式（頂欄隱現／進度條）、殼模式（tabbar／繼續閱讀卡） |
| `scripts/verify-mobile.js`（新增） | Playwright 驗收，自己起本機靜態伺服器，逐項 PASS/FAIL |
| `style.css`（修改） | 閱讀頁沉浸式、tabbar、進度條、繼續閱讀卡的樣式 |
| `build.py`（修改） | 圖片加 `id="pN"`、`<body data-ep>`、產固定頂欄與進度條、掛 `app.js`、SHELL 加 `app.js` |
| `index.html` / `char-*.html`（修改） | 加一行 `<script src="app.js" defer></script>` |

---

## Task 1: 驗收骨架

**Files:**
- Create: `scripts/verify-mobile.js`

**Interfaces:**
- Produces: `scripts/verify-mobile.js`，一支可獨立執行的驗收腳本。後續每個任務都往裡面加一個 `check(...)`，最後印出總結並在有 FAIL 時 `exit 1`。

- [ ] **Step 1: 寫驗收腳本骨架與第一個檢查**

建立 `scripts/verify-mobile.js`：

```js
/* 行動版驗收:用 iPhone 13 的實際尺寸跑,驗 DOM 與座標,不是看截圖像不像。
   跑法: NODE_PATH=$(npm root -g) node scripts/verify-mobile.js
   全域裝的是 playwright@1.54.1;這個 repo 沒有 package.json,不要新增。 */
const { chromium, devices } = require('playwright');
const { spawn } = require('child_process');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const PORT = 8899;
const BASE = `http://127.0.0.1:${PORT}`;

const results = [];
function check(name, ok, detail) {
  results.push({ name, ok, detail });
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? '  — ' + detail : ''}`);
}

function serve() {
  const p = spawn('python3', ['-m', 'http.server', String(PORT), '--bind', '127.0.0.1'],
    { cwd: ROOT, stdio: 'ignore' });
  return p;
}

async function waitForServer() {
  for (let i = 0; i < 50; i++) {
    try {
      const r = await fetch(BASE + '/index.html');
      if (r.ok) return;
    } catch (e) { /* 還沒起來 */ }
    await new Promise(r => setTimeout(r, 100));
  }
  throw new Error('本機伺服器沒起來');
}

async function main() {
  const server = serve();
  try {
    await waitForServer();
    const browser = await chromium.launch();
    const ctx = await browser.newContext({ ...devices['iPhone 13'] });
    const page = await ctx.newPage();

    // ── 檢查:站台起得來,首頁標題正確 ──
    await page.goto(BASE + '/index.html');
    const title = await page.title();
    check('首頁載入', title.includes('轉生成貓貓的我們'), title);

    await browser.close();
  } finally {
    server.kill();
  }

  const failed = results.filter(r => !r.ok);
  console.log(`\n${results.length - failed.length}/${results.length} 通過`);
  process.exit(failed.length ? 1 : 0);
}

main().catch(e => { console.error(e); process.exit(1); });
```

- [ ] **Step 2: 跑一次確認骨架會動**

```bash
cd ~/neko-tensei && NODE_PATH=$(npm root -g) node scripts/verify-mobile.js
```

Expected：印出 `PASS  首頁載入`，然後 `1/1 通過`，離開碼 0。

- [ ] **Step 3: Commit**

```bash
git add scripts/verify-mobile.js
git commit -m "test: 行動版驗收骨架——iPhone 13 實尺寸跑,自己起靜態伺服器"
```

---

## Task 2: 閱讀頁的圖片 id 與滿版

**Files:**
- Modify: `build.py`（`build_episode`）
- Modify: `style.css`（附加）
- Modify: `scripts/verify-mobile.js`

**Interfaces:**
- Consumes: Task 1 的 `check()` 與伺服器骨架
- Produces: `ep*.html` 的每張圖有 `id="p0"`…`id="p6"`（`p0` 是封面），`<body data-ep="2">`。後續任務靠這兩者定位。

- [ ] **Step 1: 先加驗收檢查（會失敗）**

在 `scripts/verify-mobile.js` 的 `await browser.close();` 之前插入：

```js
    // ── 檢查:閱讀頁每張圖有 id,且手機上滿版 ──
    await page.goto(BASE + '/ep2.html');
    const ids = await page.$$eval('main.reader img', els => els.map(e => e.id));
    check('閱讀頁圖片有 id', ids.length === 7 && ids[0] === 'p0' && ids[6] === 'p6', ids.join(','));

    const epAttr = await page.getAttribute('body', 'data-ep');
    check('body 有 data-ep', epAttr === '2', String(epAttr));

    const vw = page.viewportSize().width;
    const imgW = await page.$eval('#p1', e => e.getBoundingClientRect().width);
    check('手機上圖片滿版', Math.abs(imgW - vw) < 1, `img ${imgW} vs viewport ${vw}`);
```

- [ ] **Step 2: 跑驗收確認失敗**

```bash
cd ~/neko-tensei && NODE_PATH=$(npm root -g) node scripts/verify-mobile.js
```

Expected：`FAIL  閱讀頁圖片有 id`、`FAIL  body 有 data-ef`（`data-ep` 為 null）、`FAIL  手機上圖片滿版`（目前 `.reader` 有 `max-width:720px`，但 iPhone 13 寬 390，其實會滿版——這一項可能已經 PASS，那就只有前兩項失敗）。

- [ ] **Step 3: `build.py` 產出 id 與 data-ep**

在 `build.py` 的 `HEAD` 樣板，把 `</head><body>` 改成：

```python
</head><body data-ep="{n}">
```

在 `build_episode` 裡，把產圖那段：

```python
    for i, p in enumerate(ep['pages']):
        extra = ' fetchpriority="high"' if i == 0 else ' loading="lazy"'
        out.append(f'  <img src="images/ep{ep["n"]}/{p["f"]}" width="1024" height="1536"{extra}\n'
                   f'       alt="{p["alt"]}">\n')
```

改成：

```python
    for i, p in enumerate(ep['pages']):
        extra = ' fetchpriority="high"' if i == 0 else ' loading="lazy"'
        out.append(f'  <img id="p{i}" src="images/ep{ep["n"]}/{p["f"]}"\n'
                   f'       width="1024" height="1536"{extra}\n'
                   f'       alt="{p["alt"]}">\n')
```

- [ ] **Step 4: CSS 手機滿版**

在 `style.css` 最後附加：

```css

/* ── 行動版:閱讀頁滿版,要的是連續感 ── */
@media(max-width:720px){
  .reader{max-width:none}
  .reader img{margin:0 0 2px;border-radius:0}
}
```

- [ ] **Step 5: 重建並跑驗收**

```bash
cd ~/neko-tensei && python3 build.py && NODE_PATH=$(npm root -g) node scripts/verify-mobile.js
```

Expected：四項全 PASS。

- [ ] **Step 6: Commit**

```bash
git add build.py style.css scripts/verify-mobile.js ep1.html ep2.html
git commit -m "feat(reader): 圖片加 id 與 data-ep,手機上滿版"
```

---

## Task 3: 閱讀頁固定頂欄與自動隱現

**Files:**
- Modify: `build.py`（`HEAD` 樣板）
- Create: `app.js`
- Modify: `style.css`
- Modify: `scripts/verify-mobile.js`
- Modify: `index.html`, `char-xiaoniao.html`, `char-xiaobai.html`, `char-uncle.html`, `char-leo.html`, `char-kojiro.html`（各加一行 script）

**Interfaces:**
- Consumes: Task 2 的 `data-ep` 與圖片 id
- Produces: `app.js` 匯出（掛在 window 上不需要，全部包在 IIFE 內）；`.reader-top` 元素與其 `.hide` class；`readProgress()` / `writeProgress(ep, page)` 兩個內部函式供 Task 5、7 使用

- [ ] **Step 1: 先加驗收檢查（會失敗）**

在 `scripts/verify-mobile.js` 的 `await browser.close();` 之前插入：

```js
    // ── 檢查:閱讀頁頂欄固定且自動隱現 ──
    await page.goto(BASE + '/ep2.html');
    const topBox0 = await page.$eval('.reader-top', e => e.getBoundingClientRect().top);
    check('頂欄一開始可見', Math.abs(topBox0) < 1, String(topBox0));

    await page.evaluate(() => window.scrollTo(0, innerHeight * 2));
    await page.waitForTimeout(400);
    const topBox1 = await page.$eval('.reader-top', e => e.getBoundingClientRect().bottom);
    check('往下捲頂欄收起', topBox1 <= 0.5, String(topBox1));

    await page.evaluate(() => window.scrollBy(0, -200));
    await page.waitForTimeout(400);
    const topBox2 = await page.$eval('.reader-top', e => e.getBoundingClientRect().top);
    check('往上捲頂欄滑回', Math.abs(topBox2) < 1, String(topBox2));
```

- [ ] **Step 2: 跑驗收確認失敗**

```bash
cd ~/neko-tensei && NODE_PATH=$(npm root -g) node scripts/verify-mobile.js
```

Expected：`FAIL` 且錯誤訊息是找不到 `.reader-top`。

- [ ] **Step 3: `build.py` 產固定頂欄**

在 `build.py` 的 `HEAD` 樣板，把這一段：

```python
<div class="wrap">
  <nav class="top">
    <img src="icon-192.png" alt="" width="34" height="34">
    <a class="site" href="./">{site}</a>
    <span class="sp"></span>
    <a href="./#characters">角色</a>
  </nav>
</div>

<main class="reader">
```

換成：

```python
<nav class="reader-top">
  <a class="back" href="./" aria-label="回首頁">‹</a>
  <span class="ttl">{h1}</span>
  <a class="eps" href="./#episodes" aria-label="話數">☰</a>
</nav>

<main class="reader">
```

並在 `HEAD` 樣板的 `<link rel="stylesheet" href="style.css">` 下一行加：

```python
<script src="app.js" defer></script>
```

- [ ] **Step 4: 建立 `app.js`**

```js
/* 全站行動版行為。閱讀頁與其他頁共用一支,靠有沒有 main.reader 分流。
   進度存 localStorage,key 一律 nt- 前綴——yazelin.github.io 是所有 Pages
   專案共用的 origin,用通名會跟別的專案互相覆蓋。 */
(function () {
  'use strict';

  var KEY = 'nt-progress';

  function readProgress() {
    try { return JSON.parse(localStorage.getItem(KEY)) || null; } catch (e) { return null; }
  }
  function writeProgress(ep, page) {
    try {
      localStorage.setItem(KEY, JSON.stringify({ ep: ep, page: page, at: Date.now() }));
    } catch (e) { /* 無痕模式寫不進去就算了,不影響閱讀 */ }
  }
  function throttle(fn, ms) {
    var last = 0, timer = null;
    return function () {
      var now = Date.now(), wait = ms - (now - last);
      if (wait <= 0) { last = now; fn(); }
      else { clearTimeout(timer); timer = setTimeout(function () { last = Date.now(); fn(); }, wait); }
    };
  }

  function initReader(reader) {
    // 頂欄自動隱現:門檻 8px,手指微抖不要閃;第一個螢幕高度內永遠顯示。
    // 沒有頂欄就跳過這段,但不要 return——後面還有進度條要初始化。
    var top = document.querySelector('.reader-top');
    if (top) {
      var lastY = window.scrollY, THRESHOLD = 8;
      window.addEventListener('scroll', function () {
        var y = window.scrollY;
        if (Math.abs(y - lastY) < THRESHOLD) return;
        if (y > window.innerHeight && y > lastY) top.classList.add('hide');
        else top.classList.remove('hide');
        lastY = y;
      }, { passive: true });
    }
  }

  function boot() {
    var reader = document.querySelector('main.reader');
    if (reader) initReader(reader);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
```

- [ ] **Step 5: CSS**

在 `style.css` 最後附加：

```css

/* ── 行動版:閱讀頁固定頂欄 ── */
.reader-top{position:fixed;top:0;left:0;right:0;z-index:100;
  display:flex;align-items:center;gap:.8rem;padding:.7rem 1rem;
  background:rgba(18,20,29,.92);backdrop-filter:blur(8px);
  border-bottom:1px solid var(--line);
  transition:transform .25s ease}
.reader-top.hide{transform:translateY(-100%)}
.reader-top .back,.reader-top .eps{color:var(--ink-dim);font-size:1.3rem;line-height:1;flex:none}
.reader-top .back:hover,.reader-top .eps:hover{color:var(--gold)}
.reader-top .ttl{flex:1;min-width:0;font-size:.95rem;color:var(--ink);
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.reader{padding-top:52px}
```

- [ ] **Step 6: 其他頁掛上 `app.js`**

在 `index.html`、`char-xiaoniao.html`、`char-xiaobai.html`、`char-uncle.html`、`char-leo.html`、`char-kojiro.html` 六個檔案的 `<link rel="stylesheet" href="style.css">` 下一行，各加一行：

```html
<script src="app.js" defer></script>
```

- [ ] **Step 7: 重建並跑驗收**

```bash
cd ~/neko-tensei && python3 build.py && NODE_PATH=$(npm root -g) node scripts/verify-mobile.js
```

Expected：新增的三項全 PASS。

- [ ] **Step 8: Commit**

```bash
git add app.js build.py style.css scripts/verify-mobile.js index.html char-*.html ep1.html ep2.html
git commit -m "feat(reader): 固定頂欄與自動隱現"
```

---

## Task 4: 閱讀頁進度條與頁碼

**Files:**
- Modify: `build.py`（`build_episode` 尾端）
- Modify: `app.js`
- Modify: `style.css`
- Modify: `scripts/verify-mobile.js`

**Interfaces:**
- Consumes: Task 2 的圖片 id、Task 3 的 `initReader`
- Produces: `.progress > i`（進度寬度）與 `.progress > span`（`3/7` 文字）

- [ ] **Step 1: 先加驗收檢查（會失敗）**

在 `scripts/verify-mobile.js` 的 `await browser.close();` 之前插入：

```js
    // ── 檢查:進度條頁碼跟著實際看到的那張圖走 ──
    await page.goto(BASE + '/ep2.html');
    await page.waitForTimeout(300);
    check('進度條初始為 1/7', (await page.textContent('.progress > span')) === '1/7',
      await page.textContent('.progress > span'));

    // 把第 4 張圖(p3)捲到視窗中線
    await page.evaluate(() => {
      const el = document.getElementById('p3');
      const y = el.offsetTop + el.offsetHeight / 2 - innerHeight / 2;
      window.scrollTo(0, y);
    });
    await page.waitForTimeout(400);
    check('捲到 p3 時顯示 4/7', (await page.textContent('.progress > span')) === '4/7',
      await page.textContent('.progress > span'));
```

- [ ] **Step 2: 跑驗收確認失敗**

```bash
cd ~/neko-tensei && NODE_PATH=$(npm root -g) node scripts/verify-mobile.js
```

Expected：`FAIL`，找不到 `.progress > span`。

- [ ] **Step 3: `build.py` 產進度條**

在 `build.py` 的 `build_episode`，把：

```python
    out.append('  </nav>\n</main>\n\n')
    out.append(FOOTER)
```

改成：

```python
    out.append('  </nav>\n</main>\n\n')
    out.append(f'<div class="progress" aria-hidden="true"><i></i>'
               f'<span>1/{len(ep["pages"])}</span></div>\n\n')
    out.append(FOOTER)
```

- [ ] **Step 4: `app.js` 接上 IntersectionObserver**

在 `app.js` 的 `initReader` 函式尾端（頂欄那個 `if (top) { … }` 區塊之後）加入：

```js
    // 目前在第幾張:用 IntersectionObserver 抓通過視窗中線的那張。
    // 不要算捲動百分比——.credit 與 .reader-nav 會讓百分比失真。
    var imgs = reader.querySelectorAll('img[id^="p"]');
    var bar = document.querySelector('.progress > i');
    var num = document.querySelector('.progress > span');
    if (!imgs.length || !bar || !num) return;

    var total = imgs.length, cur = -1;
    var save = throttle(function () { writeProgress(+document.body.dataset.ep, cur); }, 500);

    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        var n = +e.target.id.slice(1);
        if (n === cur) return;
        cur = n;
        bar.style.width = ((cur + 1) / total * 100) + '%';
        num.textContent = (cur + 1) + '/' + total;
        save();
      });
    }, { rootMargin: '-50% 0px -50% 0px' });   // root 縮成視窗中線那一條

    imgs.forEach(function (img) { io.observe(img); });
```

- [ ] **Step 5: CSS**

在 `style.css` 最後附加：

```css

/* ── 行動版:閱讀進度條 ── */
.progress{position:fixed;left:0;right:0;bottom:0;z-index:100;height:3px;
  background:rgba(255,255,255,.12);
  padding-bottom:env(safe-area-inset-bottom,0px)}
.progress > i{display:block;height:3px;width:14%;background:var(--gold);
  transition:width .25s ease}
.progress > span{position:absolute;right:.6rem;
  bottom:calc(.6rem + env(safe-area-inset-bottom,0px));
  font-size:.72rem;letter-spacing:.06em;color:var(--ink-dim);
  background:rgba(18,20,29,.78);padding:.12rem .5rem;border-radius:10px}
```

- [ ] **Step 6: 重建並跑驗收**

```bash
cd ~/neko-tensei && python3 build.py && NODE_PATH=$(npm root -g) node scripts/verify-mobile.js
```

Expected：新增的兩項 PASS。

- [ ] **Step 7: Commit**

```bash
git add build.py app.js style.css scripts/verify-mobile.js ep1.html ep2.html
git commit -m "feat(reader): 底部進度條與頁碼,用 IntersectionObserver 抓中線"
```

---

## Task 5: 進度儲存

**Files:**
- Modify: `scripts/verify-mobile.js`

**Interfaces:**
- Consumes: Task 4 已經呼叫 `writeProgress`，這個任務只補驗證

- [ ] **Step 1: 加驗收檢查**

在 `scripts/verify-mobile.js` 的 `await browser.close();` 之前插入：

```js
    // ── 檢查:進度寫進 localStorage,且 key 有 nt- 前綴 ──
    await page.goto(BASE + '/ep2.html');
    await page.evaluate(() => {
      const el = document.getElementById('p3');
      window.scrollTo(0, el.offsetTop + el.offsetHeight / 2 - innerHeight / 2);
    });
    await page.waitForTimeout(900);   // 等節流的 500ms 過去
    const saved = await page.evaluate(() => localStorage.getItem('nt-progress'));
    let ok = false, parsed = null;
    try { parsed = JSON.parse(saved); ok = parsed && parsed.ep === 2 && parsed.page === 3; } catch (e) {}
    check('進度寫入 nt-progress', ok, saved);

    const keys = await page.evaluate(() => Object.keys(localStorage));
    check('localStorage 的 key 都有 nt- 前綴',
      keys.every(k => k.indexOf('nt-') === 0), keys.join(','));
```

- [ ] **Step 2: 跑驗收**

```bash
cd ~/neko-tensei && NODE_PATH=$(npm root -g) node scripts/verify-mobile.js
```

Expected：兩項 PASS（Task 4 已經實作了 `writeProgress`）。若 `FAIL`，檢查 `document.body.dataset.ep` 是否為 `"2"`（Task 2 的 `data-ep`）。

- [ ] **Step 3: Commit**

```bash
git add scripts/verify-mobile.js
git commit -m "test: 驗進度寫入 nt-progress 且 key 有前綴"
```

---

## Task 6: 首頁與角色頁的底部 tabbar

**Files:**
- Modify: `app.js`
- Modify: `style.css`
- Modify: `scripts/verify-mobile.js`

**Interfaces:**
- Consumes: Task 3 的 `boot()` 分流
- Produces: `nav.tabbar` 元素、CSS 變數 `--tabbar-h`

- [ ] **Step 1: 先加驗收檢查（會失敗）**

在 `scripts/verify-mobile.js` 的 `await browser.close();` 之前插入：

```js
    // ── 檢查:首頁 tabbar 固定在底部且沒被 home indicator 蓋住 ──
    await page.goto(BASE + '/index.html');
    await page.waitForTimeout(300);
    const vh = page.viewportSize().height;
    const tb = await page.$eval('.tabbar', e => {
      const r = e.getBoundingClientRect();
      return { top: r.top, bottom: r.bottom, h: r.height };
    });
    check('tabbar 貼在視窗底部', Math.abs(tb.bottom - vh) < 1, JSON.stringify(tb));

    const tabs = await page.$$eval('.tabbar > *', els => els.map(e => e.textContent.trim()));
    check('tabbar 有四格', tabs.length === 4, tabs.join('/'));

    const varH = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--tabbar-h').trim());
    check('--tabbar-h 有量出來', parseFloat(varH) > 30, varH);

    const padB = await page.evaluate(() =>
      parseFloat(getComputedStyle(document.body).paddingBottom));
    check('內容底部有留出 tabbar 的高度', padB >= tb.h - 1, `${padB} vs ${tb.h}`);

    // 第四格在沒有 beforeinstallprompt 的環境(等同 iOS)要是「關於」,不是死按鈕
    check('第四格降級為關於', tabs[3] === '關於', tabs[3]);
```

- [ ] **Step 2: 跑驗收確認失敗**

```bash
cd ~/neko-tensei && NODE_PATH=$(npm root -g) node scripts/verify-mobile.js
```

Expected：`FAIL`，找不到 `.tabbar`。

- [ ] **Step 3: `app.js` 注入 tabbar**

在 `app.js` 的 IIFE 內、`boot()` 之前加入：

```js
  var IC = {
    home: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 2 12h3v9h6v-6h2v6h6v-9h3z"/></svg>',
    eps:  '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 5h18v2H3zm0 6h18v2H3zm0 6h18v2H3z"/></svg>',
    char: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm0 2c-4 0-8 2-8 5v1h16v-1c0-3-4-5-8-5z"/></svg>',
    down: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v10l4-4 1.4 1.4L12 16.8 6.6 10.4 8 9l4 4V3zM4 19h16v2H4z"/></svg>',
    info: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm1 15h-2v-6h2zm0-8h-2V7h2z"/></svg>'
  };

  function initShell() {
    if (document.querySelector('.tabbar')) return;

    var nav = document.createElement('nav');
    nav.className = 'tabbar';
    nav.setAttribute('aria-label', '主選單');
    nav.innerHTML =
      '<a href="./#top">' + IC.home + '<span>首頁</span></a>' +
      '<a href="./#episodes">' + IC.eps + '<span>話數</span></a>' +
      '<a href="./#characters">' + IC.char + '<span>角色</span></a>' +
      '<button type="button" id="tab4">' + IC.info + '<span>關於</span></button>';
    document.body.appendChild(nav);

    // 第四格預設是「關於」。只有 beforeinstallprompt 真的觸發了才換成「安裝」——
    // iOS Safari 永遠不會觸發,不要留一個按了沒反應的按鈕。
    var slot = nav.querySelector('#tab4');
    slot.addEventListener('click', function () { location.hash = '#origin'; });

    window.addEventListener('beforeinstallprompt', function (e) {
      e.preventDefault();
      var deferred = e;
      slot.innerHTML = IC.down + '<span>安裝</span>';
      slot.onclick = function () {
        deferred.prompt();
        deferred.userChoice.then(function () { deferred = null; });
      };
    });

    function measure() {
      document.documentElement.style.setProperty('--tabbar-h', nav.offsetHeight + 'px');
    }
    measure();
    window.addEventListener('resize', measure);
  }
```

並把 `boot()` 改成：

```js
  function boot() {
    var reader = document.querySelector('main.reader');
    if (reader) initReader(reader);
    else initShell();
  }
```

- [ ] **Step 4: CSS**

在 `style.css` 最後附加：

```css

/* ── 行動版:底部 tabbar ── */
.tabbar{display:none}
@media(max-width:720px){
  .tabbar{display:flex;position:fixed;left:0;right:0;bottom:0;z-index:150;
    background:rgba(18,20,29,.96);border-top:1px solid var(--line);
    padding-bottom:env(safe-area-inset-bottom,0px)}
  .tabbar > *{flex:1;display:flex;flex-direction:column;align-items:center;gap:.15rem;
    padding:.5rem 0 .45rem;background:none;border:0;cursor:pointer;
    color:var(--ink-dim);font:inherit;font-size:.68rem;letter-spacing:.06em}
  .tabbar svg{width:20px;height:20px;fill:currentColor}
  .tabbar > *:hover{color:var(--gold)}
  body{padding-bottom:var(--tabbar-h,56px)}
  #inst{display:none!important}   /* 安裝鈕在 tabbar,首頁不重複放 */
}
```

- [ ] **Step 5: 跑驗收**

```bash
cd ~/neko-tensei && NODE_PATH=$(npm root -g) node scripts/verify-mobile.js
```

Expected：新增的五項全 PASS。

- [ ] **Step 6: Commit**

```bash
git add app.js style.css scripts/verify-mobile.js
git commit -m "feat(shell): 行動版底部 tabbar,第四格在 iOS 降級為關於"
```

---

## Task 7: 首頁「繼續閱讀」卡

**Files:**
- Modify: `app.js`
- Modify: `style.css`
- Modify: `scripts/verify-mobile.js`

**Interfaces:**
- Consumes: Task 3 的 `readProgress()`、Task 6 的 `initShell()`
- Produces: `a.resume` 元素，`href` 形如 `ep2.html#p3`

- [ ] **Step 1: 先加驗收檢查（會失敗）**

在 `scripts/verify-mobile.js` 的 `await browser.close();` 之前插入：

```js
    // ── 檢查:沒有紀錄時,繼續閱讀卡不出現 ──
    await page.goto(BASE + '/index.html');
    await page.evaluate(() => localStorage.clear());
    await page.reload();
    await page.waitForTimeout(300);
    check('沒紀錄時不顯示繼續閱讀', (await page.$('.resume')) === null);

    // ── 檢查:有紀錄時出現,且點下去落在正確那張圖 ──
    await page.evaluate(() => localStorage.setItem('nt-progress',
      JSON.stringify({ ep: 2, page: 3, at: Date.now() })));
    await page.reload();
    await page.waitForTimeout(300);
    const href = await page.getAttribute('.resume', 'href');
    check('繼續閱讀連到正確位置', /ep2\.html#p3$/.test(href || ''), String(href));

    await page.click('.resume');
    await page.waitForTimeout(600);
    const landed = await page.evaluate(() => {
      const el = document.getElementById('p3');
      return Math.abs(el.getBoundingClientRect().top);
    });
    check('跳轉落在 p3 上緣', landed < 80, String(landed));
```

- [ ] **Step 2: 跑驗收確認失敗**

```bash
cd ~/neko-tensei && NODE_PATH=$(npm root -g) node scripts/verify-mobile.js
```

Expected：第一項 PASS（本來就沒有卡），後兩項 FAIL。

- [ ] **Step 3: `app.js` 注入繼續閱讀卡並處理 hash**

在 `app.js` 的 `initShell()` 尾端加入：

```js
    // 繼續閱讀:沒有紀錄就整張不出現,不佔位也不顯示假資料
    var prog = readProgress();
    var hero = document.querySelector('.hero');
    if (!prog || !prog.ep || !hero) return;

    var CN = ['', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十'];
    var where = prog.page === 0 ? '封面' : '第 ' + prog.page + ' 頁';
    var card = document.createElement('a');
    card.className = 'resume';
    card.href = 'ep' + prog.ep + '.html#p' + prog.page;
    card.innerHTML =
      '<span class="resume-ic" aria-hidden="true">▶</span>' +
      '<span class="resume-t">繼續閱讀<small>第' + (CN[prog.ep] || prog.ep) + '話 · ' + where + '</small></span>';
    hero.insertAdjacentElement('afterbegin', card);
```

在 `initReader()` 尾端（`imgs.forEach(...)` 之後）加入：

```js
    // 從首頁的「繼續閱讀」跳進來:圖是 lazy 的,等它有高度再捲
    if (location.hash) {
      var target = document.getElementById(location.hash.slice(1));
      if (target) {
        requestAnimationFrame(function () { target.scrollIntoView(); });
        target.addEventListener('load', function () { target.scrollIntoView(); }, { once: true });
      }
    }
```

- [ ] **Step 4: CSS**

在 `style.css` 最後附加：

```css

/* ── 首頁:繼續閱讀 ── */
.resume{display:flex;align-items:center;gap:.85rem;
  margin:0 0 1.6rem;padding:.85rem 1rem;text-align:left;
  background:var(--panel);border:1px solid var(--line);border-radius:12px;color:var(--ink)}
.resume:hover{border-color:var(--gold);color:var(--ink)}
.resume-ic{flex:none;width:34px;height:34px;display:grid;place-items:center;
  border-radius:50%;background:var(--gold);color:#241c08;font-size:.85rem}
.resume-t{font-size:.95rem;line-height:1.5}
.resume-t small{display:block;color:var(--ink-dim);font-size:.78rem;letter-spacing:.04em}
```

- [ ] **Step 5: 跑驗收**

```bash
cd ~/neko-tensei && NODE_PATH=$(npm root -g) node scripts/verify-mobile.js
```

Expected：三項全 PASS。

- [ ] **Step 6: Commit**

```bash
git add app.js style.css scripts/verify-mobile.js
git commit -m "feat(shell): 首頁繼續閱讀卡,沒紀錄就不出現"
```

---

## Task 8: 進離線快取並上線

**Files:**
- Modify: `build.py`（SHELL 清單）
- Modify: `sw.js`（版本號）
- Modify: `scripts/verify-mobile.js`

**Interfaces:**
- Consumes: 前面所有任務

- [ ] **Step 1: 加驗收檢查（會失敗）**

在 `scripts/verify-mobile.js` 的 `await browser.close();` 之前插入：

```js
    // ── 檢查:app.js 有進離線殼快取,否則離線時行動版行為全失效 ──
    const sw = await (await fetch(BASE + '/sw.js')).text();
    check('sw.js 的 SHELL 含 app.js', sw.includes("'./app.js'"));
```

- [ ] **Step 2: 跑驗收確認失敗**

```bash
cd ~/neko-tensei && NODE_PATH=$(npm root -g) node scripts/verify-mobile.js
```

Expected：`FAIL  sw.js 的 SHELL 含 app.js`。

- [ ] **Step 3: `build.py` 把 `app.js` 加進 SHELL**

在 `build.py` 的 `main()`，把：

```python
    shell.append("  './style.css', './manifest.json',")
```

改成：

```python
    shell.append("  './style.css', './app.js', './manifest.json',")
```

- [ ] **Step 4: bump 快取版本並重建**

```bash
cd ~/neko-tensei
sed -i 's/nt-shell-v9/nt-shell-v10/;s/nt-asset-v9/nt-asset-v10/' sw.js
python3 build.py
NODE_PATH=$(npm root -g) node scripts/verify-mobile.js
```

Expected：全部 PASS，最後印出 `17/17 通過`（實際數字以累積的檢查數為準）。

若 `sed` 沒有替換到（版本號已經不是 v9），先用 `grep -n "nt-shell" sw.js` 看目前版本再改。

- [ ] **Step 5: Commit 並推上線**

```bash
git add build.py sw.js scripts/verify-mobile.js ep1.html ep2.html
git commit -m "feat: 行動版閱讀體驗上線——沉浸式閱讀頁、tabbar、繼續閱讀

閱讀頁:固定頂欄自動隱現、底部進度條(IntersectionObserver 抓視窗中線,
不算捲動百分比,因為 .credit 與 .reader-nav 會讓百分比失真)、手機滿版。
首頁與角色頁:底部 tabbar,第四格在沒有 beforeinstallprompt 的環境(iOS)
降級為「關於」,不留死按鈕。進度存 nt-progress,前綴不能省——
yazelin.github.io 是所有 Pages 專案共用的 origin。"
git push
```

- [ ] **Step 6: 線上驗一次**

等 GitHub Pages 發佈後：

```bash
cd ~/neko-tensei
for i in $(seq 1 12); do
  curl -s "https://yazelin.github.io/neko-tensei/app.js?t=$RANDOM" | head -1 | grep -q "全站行動版行為" && { echo "已發佈"; break; }
  sleep 20
done
curl -s -o /dev/null -w 'app.js %{http_code}\n' https://yazelin.github.io/neko-tensei/app.js
```

Expected：`app.js 200`。

---

## 完成後

行動版做完就接**討論區**（開 GitHub Discussions ＋ 首頁掛 giscus 許願串），再接 **pipeline**。討論區排在 pipeline 前面，是為了讓 pipeline 上線時就有社群許願可以讀。
