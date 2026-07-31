/* 行動版驗收:用 iPhone 13 的實際尺寸跑,驗 DOM 與座標,不是看截圖像不像。
   跑法: NODE_PATH=$(npm root -g) node scripts/verify-mobile.js
   全域裝的是 playwright@1.54.1;這個 repo 沒有 package.json,不要新增。 */
const { chromium, devices } = require('playwright');
const { spawn } = require('child_process');
const net = require('net');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
let BASE = '';

/* Chromium 的 device emulation 不模擬 safe area,env(safe-area-inset-*) 一律回 0,
   凡是「有 inset 才會壞」的版面都驗不到。用這組固定值假裝 iPhone 的瀏海與 home
   indicator——數字取 iPhone 13 直立時的實際值。 */
const INSET = { top: 47, bottom: 34, left: 0, right: 0 };

const results = [];
function check(name, ok, detail) {
  results.push({ name, ok, detail });
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? '  — ' + detail : ''}`);
}

/* 固定 port 會撞上別的專案留在背景的 http.server——那時整輪其實是在驗別人的站,
   而且會「看起來只是壞掉」而不是「port 被佔」。改成每次要一個空的 port。 */
function freePort() {
  return new Promise((resolve, reject) => {
    const s = net.createServer();
    s.on('error', reject);
    s.listen(0, '127.0.0.1', () => {
      const p = s.address().port;
      s.close(() => resolve(p));
    });
  });
}

function serve(port) {
  return spawn('python3', ['-m', 'http.server', String(port), '--bind', '127.0.0.1'],
    { cwd: ROOT, stdio: 'ignore' });
}

async function waitForServer() {
  for (let i = 0; i < 50; i++) {
    try {
      const r = await fetch(BASE + '/index.html');
      if (r.ok) {
        const t = await r.text();
        if (!t.includes('轉生成貓貓的我們')) throw new Error(`${BASE} 上的不是這個站`);
        return;
      }
    } catch (e) {
      if (/不是這個站/.test(e.message)) throw e;   /* 還沒起來 */
    }
    await new Promise(r => setTimeout(r, 100));
  }
  throw new Error('本機伺服器沒起來');
}

/* 全程收 console error 與未捕捉例外,最後一項檢查斷言整輪乾淨。 */
const consoleErrors = [];
async function newPage(ctx) {
  const page = await ctx.newPage();
  page.on('pageerror', e => consoleErrors.push('pageerror: ' + e.message));
  page.on('console', m => {
    if (m.type() === 'error') consoleErrors.push('console: ' + m.text());
  });
  // 只印訊息看不出是哪個檔 404,把 URL 也記下來
  page.on('response', r => {
    if (r.status() === 404) consoleErrors.push('404: ' + r.url());
  });
  return page;
}

/* 在 document_start 掛鉤,載入後把 style.css 裡的 env(safe-area-inset-*) 換成
   固定 px 再整份補一次(同權重、後蓋前),用來驗有 inset 時的版面。 */
async function injectInsets(page) {
  await page.addInitScript(inset => {
    var apply = function () {
      // 從頁面上實際的 <link> 取,不要寫死 './style.css'——
      // 子目錄頁(ep/、char/)會把它解析成 /ep/style.css 然後 404。
      var link = document.querySelector('link[rel="stylesheet"]');
      if (!link) return;
      fetch(link.href).then(function (r) { return r.text(); }).then(function (css) {
        var s = document.createElement('style');
        s.id = '__insets';
        s.textContent = css.replace(
          /env\(\s*safe-area-inset-(top|bottom|left|right)\s*(?:,[^()]*)?\)/g,
          function (_, side) { return inset[side] + 'px'; });
        document.head.appendChild(s);
      });
    };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', apply);
    else apply();
  }, INSET);
}

async function main() {
  const port = await freePort();
  BASE = `http://127.0.0.1:${port}`;
  const server = serve(port);
  try {
    await waitForServer();
    const browser = await chromium.launch();
    const ctx = await browser.newContext({ ...devices['iPhone 13'] });
    const page = await newPage(ctx);

    // ── 檢查:站台起得來,首頁標題正確 ──
    await page.goto(BASE + '/index.html');
    const title = await page.title();
    check('首頁載入', title.includes('轉生成貓貓的我們'), title);

    // ── 檢查:閱讀頁每張圖有 id,且手機上滿版 ──
    await page.goto(BASE + '/ep/2.html');
    const ids = await page.$$eval('main.reader img', els => els.map(e => e.id));
    check('閱讀頁圖片有 id', ids.length === 7 && ids[0] === 'p0' && ids[6] === 'p6', ids.join(','));

    const epAttr = await page.getAttribute('body', 'data-ep');
    check('body 有 data-ep', epAttr === '2', String(epAttr));

    const vw = page.viewportSize().width;
    const imgW = await page.$eval('#p1', e => e.getBoundingClientRect().width);
    check('手機上圖片滿版', Math.abs(imgW - vw) < 1, `img ${imgW} vs viewport ${vw}`);

    // 閱讀頁沒有 tabbar,就不該吃 --tabbar-h 的 fallback——否則 footer 下面
    // 每一頁都多一塊 56px 的空白
    const readerPadB = await page.evaluate(() =>
      parseFloat(getComputedStyle(document.body).paddingBottom));
    check('閱讀頁底部沒有多餘留白', readerPadB < 1, `${readerPadB}px`);
    check('閱讀頁沒有 tabbar', (await page.$('.tabbar')) === null);

    // ── 檢查:閱讀頁頂欄固定且自動隱現 ──
    await page.goto(BASE + '/ep/2.html');
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

    // ── 檢查:進度條頁碼跟著實際看到的那張圖走 ──
    await page.goto(BASE + '/ep/2.html');
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

    // ── 檢查:進度寫進 localStorage,且 key 有 nt- 前綴 ──
    await page.goto(BASE + '/ep/2.html');
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
      keys.length > 0 && keys.every(k => k.indexOf('nt-') === 0), keys.join(','));

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

    // ── 檢查:beforeinstallprompt 觸發後,「安裝」不會疊加「關於」的跳轉 ──
    // 舊寫法用 addEventListener 註冊跳轉、又用 onclick 疊加安裝行為,兩個一起觸發,
    // 點「安裝」會意外跳去 #origin。派一個假事件模擬觸發,點下去斷言 hash 沒變。
    await page.goto(BASE + '/index.html');
    await page.waitForTimeout(300);
    await page.evaluate(() => {
      const ev = new Event('beforeinstallprompt', { cancelable: true });
      ev.prompt = () => { window.__prompted = true; };
      ev.userChoice = Promise.resolve({ outcome: 'accepted' });
      window.dispatchEvent(ev);
    });
    await page.waitForTimeout(100);
    await page.click('#tab4');
    await page.waitForTimeout(200);
    const promptCalled = await page.evaluate(() => window.__prompted === true);
    const hashAfterInstallClick = await page.evaluate(() => location.hash);
    check('安裝按鈕點下去不會疊加跳轉 #origin',
      promptCalled && hashAfterInstallClick !== '#origin',
      `prompted=${promptCalled} hash=${hashAfterInstallClick}`);

    // ── 檢查:安裝表單按「以後再說」之後,第四格要變回「關於」 ──
    // beforeinstallprompt 同一次瀏覽不會再觸發,標籤沒還原就會一路錯到重新載入,
    // 讀者以為自己在點「安裝」,實際被丟去誕生故事。
    await page.goto(BASE + '/index.html');
    await page.waitForTimeout(300);
    await page.evaluate(() => {
      const ev = new Event('beforeinstallprompt', { cancelable: true });
      ev.prompt = () => {};
      ev.userChoice = Promise.resolve({ outcome: 'dismissed' });
      window.dispatchEvent(ev);
    });
    await page.waitForTimeout(100);
    const labelBefore = await page.textContent('#tab4');
    await page.click('#tab4');
    await page.waitForTimeout(300);
    const labelAfter = await page.textContent('#tab4');
    check('取消安裝後第四格還原成「關於」',
      labelBefore.trim() === '安裝' && labelAfter.trim() === '關於',
      `${labelBefore.trim()} → ${labelAfter.trim()}`);

    // 再點一次:標籤寫什麼就要做什麼。deferred 已經被清掉,行為必定是跳 #origin,
    // 所以這裡要驗的是「按下去的當下標籤是不是還騙人寫著安裝」。
    const labelAtClick = (await page.textContent('#tab4')).trim();
    await Promise.all([
      page.waitForNavigation({ waitUntil: 'load' }).catch(() => {}),
      page.click('#tab4'),
    ]);
    await page.waitForTimeout(200);
    const hash2 = await page.evaluate(() => location.hash);
    check('取消安裝後第四格的標籤與行為一致',
      labelAtClick === '關於' && hash2 === '#origin',
      `標籤=${labelAtClick} 落點=${hash2}`);

    // ── 檢查:角色頁的「關於」要導到首頁的誕生故事,不是死連結 ──
    // 舊寫法用 location.hash = '#origin',但 char-*.html 沒有 id="origin",
    // 點下去網址變成 char-kojiro.html#origin,畫面毫無反應。
    await page.goto(BASE + '/char/kojiro.html');
    await page.waitForTimeout(300);
    await Promise.all([
      page.waitForNavigation({ waitUntil: 'load' }),
      page.click('#tab4'),
    ]);
    await page.waitForTimeout(200);
    const landed = await page.evaluate(() => ({ path: location.pathname, hash: location.hash }));
    check('角色頁「關於」落到首頁誕生故事',
      /\/(index\.html)?$/.test(landed.path) && landed.hash === '#origin',
      JSON.stringify(landed));

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
    check('繼續閱讀連到正確位置', /ep\/2\.html#p3$/.test(href || ''), String(href));

    await page.click('.resume');
    await page.waitForTimeout(600);
    const landedOffset = await page.evaluate(() => {
      const el = document.getElementById('p3');
      return Math.abs(el.getBoundingClientRect().top);
    });
    check('跳轉落在 p3 上緣', landedOffset < 80, String(landedOffset));

    // ── 檢查:繼續閱讀卡只在首頁,角色頁不能出現(即使有紀錄) ──
    await page.goto(BASE + '/char/kojiro.html');
    await page.waitForTimeout(300);
    check('角色頁不顯示繼續閱讀', (await page.$('.resume')) === null);

    // ── 檢查:nt-progress 是髒的就整張不出現,更不能把內容注進 DOM ──
    // yazelin.github.io 是所有 Pages 專案共用的 origin,這個 key 別的專案寫得進來。
    const dirty = [
      ['缺 page', { ep: 2 }],
      ['話數不存在', { ep: 99, page: 3 }],
      ['ep 帶標籤', { ep: '<img src=x onerror="window.__xss=1">', page: 1 }],
      ['page 帶標籤', { ep: 2, page: '<img src=x onerror="window.__xss=1">' }],
      ['page 為負', { ep: 2, page: -1 }],
      ['page 非整數', { ep: 2, page: 1.5 }],
    ];
    const bad = [];
    for (const [label, payload] of dirty) {
      await page.goto(BASE + '/index.html');
      await page.evaluate(p => localStorage.setItem('nt-progress', JSON.stringify(p)), payload);
      await page.reload();
      await page.waitForTimeout(250);
      const state = await page.evaluate(() => ({
        card: !!document.querySelector('.resume'),
        injected: !!document.querySelector('.hero img[src="x"]'),
        xss: window.__xss === true,
      }));
      if (state.card || state.injected || state.xss) bad.push(label + ':' + JSON.stringify(state));
    }
    check('髒的 nt-progress 不出卡也不注入 DOM', bad.length === 0, bad.join(' | '));

    // ── 檢查:app.js 有進離線殼快取,否則離線時行動版行為全失效 ──
    // 只在 shell 區塊裡找:整份檔案做字串比對的話,app.js 掉到 WARM 也會通過。
    const sw = await (await fetch(BASE + '/sw.js')).text();
    const s0 = sw.indexOf('/* shell:start */'), s1 = sw.indexOf('/* shell:end */');
    const shellBlock = s0 >= 0 && s1 > s0 ? sw.slice(s0, s1) : '';
    check('sw.js 的 SHELL 區塊含 app.js', shellBlock.includes("'./app.js'"),
      shellBlock ? '' : '找不到 shell 標記');

    // ── 檢查:有 safe area 的機型上,版面是「墊高」而不是「變成一片色塊」 ──
    // Chromium 不模擬 inset,不注入固定值的話這幾項在 inset=0 時必然成立。
    const ctxI = await browser.newContext({ ...devices['iPhone 13'] });
    const pageI = await newPage(ctxI);
    await injectInsets(pageI);

    await pageI.goto(BASE + '/ep/2.html');
    await pageI.waitForFunction(() => !!document.getElementById('__insets'));
    await pageI.waitForTimeout(200);
    const pr = await pageI.$eval('.progress', e => {
      const r = e.getBoundingClientRect();
      const i = e.querySelector('i').getBoundingClientRect();
      return { h: r.height, bottom: r.bottom, barH: i.height, barTop: i.top - r.top };
    });
    const vhI = pageI.viewportSize().height;
    check('有 inset 時進度條只墊高、不變成色塊',
      Math.abs(pr.h - (3 + INSET.bottom)) < 1 && Math.abs(pr.bottom - vhI) < 1,
      JSON.stringify(pr));
    check('有 inset 時金色進度條仍是 3px 且貼在軌道頂端',
      Math.abs(pr.barH - 3) < 1 && Math.abs(pr.barTop) < 1, JSON.stringify(pr));

    const rt = await pageI.$eval('.reader-top', e => ({
      padTop: parseFloat(getComputedStyle(e).paddingTop),
      bottom: e.getBoundingClientRect().bottom,
    }));
    const firstImgTop = await pageI.$eval('#p0', e => e.getBoundingClientRect().top);
    check('有 inset 時頂欄避開狀態列',
      rt.padTop >= INSET.top && firstImgTop >= rt.bottom - 1,
      `padTop=${rt.padTop} 頂欄底=${rt.bottom} 第一張圖=${firstImgTop}`);

    await pageI.goto(BASE + '/index.html');
    await pageI.waitForFunction(() => !!document.getElementById('__insets'));
    await pageI.waitForTimeout(300);
    const tbI = await pageI.$eval('.tabbar', e => ({
      h: e.getBoundingClientRect().height,
      bottom: e.getBoundingClientRect().bottom,
      padB: parseFloat(getComputedStyle(e).paddingBottom),
    }));
    check('有 inset 時 tabbar 往上墊高且仍貼底',
      Math.abs(tbI.padB - INSET.bottom) < 1 &&
      Math.abs(tbI.h - (tb.h + INSET.bottom)) < 1 &&
      Math.abs(tbI.bottom - vhI) < 1,
      `${JSON.stringify(tbI)} vs 無 inset 高度 ${tb.h}`);

    await ctxI.close();

    // ── 檢查:JS 沒跑時,進度條不顯示寫死的假進度 ──
    // 擋掉 app.js 來模擬。這一頁的載入錯誤是故意製造的,不掛 console 收集。
    const ctxNoJs = await browser.newContext({ ...devices['iPhone 13'] });
    await ctxNoJs.route('**/app.js', r => r.abort());
    const pageN = await ctxNoJs.newPage();
    await pageN.goto(BASE + '/ep/2.html');
    await pageN.waitForTimeout(200);
    const barNoJs = await pageN.$eval('.progress > i', e => e.getBoundingClientRect().width);
    check('沒有 JS 時進度條不顯示假進度', barNoJs < 1, `${barNoJs}px`);
    await ctxNoJs.close();


    // ── 檢查:討論區佔位存在,且捲到之前不該載入第三方 script ──
    await page.goto(BASE + '/index.html');
    await page.waitForTimeout(300);
    const gis = await page.$eval('#giscus', e => ({
      cat: e.dataset.categoryId, map: e.dataset.mapping, term: e.dataset.term || ''
    })).catch(() => null);
    check('首頁有劇情許願佔位',
      !!gis && gis.map === 'specific' && gis.term === '劇情許願' && /^DIC_/.test(gis.cat),
      JSON.stringify(gis));

    const beforeScroll = await page.$$eval('script[src*="giscus.app"]', els => els.length);
    check('沒捲到就不載入 giscus', beforeScroll === 0, String(beforeScroll));

    await page.evaluate(() => document.getElementById('giscus').scrollIntoView());
    await page.waitForTimeout(600);
    const afterScroll = await page.$$eval('script[src*="giscus.app"]', els => els.length);
    check('捲到才載入 giscus', afterScroll === 1, String(afterScroll));

    await page.goto(BASE + '/ep/2.html');
    await page.waitForTimeout(300);
    const gis2 = await page.$eval('#giscus', e => ({
      cat: e.dataset.categoryId, map: e.dataset.mapping, term: e.dataset.term || ''
    })).catch(() => null);
    check('閱讀頁有每話討論佔位(pathname 對應,無 term)',
      !!gis2 && gis2.map === 'pathname' && gis2.term === '' && /^DIC_/.test(gis2.cat),
      JSON.stringify(gis2));

    check('兩處用不同分類', !!gis && !!gis2 && gis.cat !== gis2.cat,
      `${gis && gis.cat} vs ${gis2 && gis2.cat}`);


    // ── 檢查:sw.js 不能用全域 caches.match() 服務非 HTML 資源 ──
    // 全域 match 會搜遍所有快取,把執行期 ASSET 裡的舊 style.css / app.js
    // 撈出來蓋掉新版;而 ASSET 只有換圖才 bump,那種副本會活很久。
    // 這個 bug 讓討論區的 CSS/JS 上線後在瀏覽器上完全沒生效。
    {
      const swSrc = await (await fetch(BASE + '/sw.js')).text();
      const assetBranch = swSrc.slice(swSrc.indexOf('} else {'));
      check('sw.js 的非 HTML 分支不用全域 caches.match',
        !/caches\.match\(/.test(assetBranch), assetBranch.slice(0, 80).replace(/\n/g, ' '));
      check('sw.js 有殼檔網址集合可用來分流', /SHELL_URLS/.test(swSrc));
      check('sw.js 會清掉 ASSET 裡誤存的殼檔',
        /a\.delete\(r\)/.test(swSrc) || /\.delete\(r\)/.test(swSrc));
    }

    await browser.close();

    check('整輪沒有 console error 或 pageerror', consoleErrors.length === 0,
      consoleErrors.slice(0, 5).join(' | '));
  } finally {
    server.kill();
  }

  const failed = results.filter(r => !r.ok);
  console.log(`\n${results.length - failed.length}/${results.length} 通過`);
  process.exit(failed.length ? 1 : 0);
}

main().catch(e => { console.error(e); process.exit(1); });
