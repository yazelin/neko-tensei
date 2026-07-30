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

    // ── 檢查:閱讀頁每張圖有 id,且手機上滿版 ──
    await page.goto(BASE + '/ep2.html');
    const ids = await page.$$eval('main.reader img', els => els.map(e => e.id));
    check('閱讀頁圖片有 id', ids.length === 7 && ids[0] === 'p0' && ids[6] === 'p6', ids.join(','));

    const epAttr = await page.getAttribute('body', 'data-ep');
    check('body 有 data-ep', epAttr === '2', String(epAttr));

    const vw = page.viewportSize().width;
    const imgW = await page.$eval('#p1', e => e.getBoundingClientRect().width);
    check('手機上圖片滿版', Math.abs(imgW - vw) < 1, `img ${imgW} vs viewport ${vw}`);

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

    await browser.close();
  } finally {
    server.kill();
  }

  const failed = results.filter(r => !r.ok);
  console.log(`\n${results.length - failed.length}/${results.length} 通過`);
  process.exit(failed.length ? 1 : 0);
}

main().catch(e => { console.error(e); process.exit(1); });
