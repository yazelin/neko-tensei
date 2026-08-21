/* 主題曲播放器驗收:歌詞對齊到哪一行、能不能播、有沒有 console 錯誤。
   跑法: NODE_PATH=$(npm root -g) node scripts/verify-music.js
   這個 repo 沒有 package.json,不要新增。全域那份若沒跑過 `npx playwright install`
   會缺瀏覽器,把 NODE_PATH 指到任何裝好 playwright 的 node_modules 也可以。

   驗的是「時間 → 哪一行亮」這條邏輯,不是聽起來對不對——時間軸本身是
   whisper 逐字時間戳加人工定錨定出來的,要改就改 assets/theme-song.lrc。 */
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');

/* 取樣點:每段各挑一句,含刻意挑在「上一行還沒換掉」的邊界前後 */
const SAMPLES = [
  [2.0, null],                          // 前奏,還沒有歌詞
  [6.0, '深夜加班寫程式 螢幕閃著藍色光'],
  [11.5, '深夜加班寫程式 螢幕閃著藍色光'],   // 邊界前 0.1 秒還是上一行
  [11.7, '突然腳下魔法陣 咻一聲全被吸走啦'],
  [30.0, '喵喵喵 貓貓進行曲'],
  [48.0, '喵喵喵 貓貓進行曲'],            // 歌詞單裡沒有、但真的唱了的 hook 重複段
  [57.0, '小鳥不啾唸咒語 魔力不足加 Token'],
  [95.0, 'Merge Conflict 石巨人擋在路中間'],
  [111.0, '四隻貓坐在草地 望著月亮打呵欠'],
  [130.0, '我們是異世界的 工程師貓貓隊'],
  [140.0, '喵……'],
];

const results = [];
function check(name, ok, detail) {
  results.push({ name, ok, detail });
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? '  — ' + detail : ''}`);
}

function serve() {
  const proc = spawn('python3', ['-u', '-m', 'http.server', '0', '--bind', '127.0.0.1'],
    { cwd: ROOT, stdio: ['ignore', 'pipe', 'ignore'] });
  return new Promise((resolve, reject) => {
    let buf = '';
    const timer = setTimeout(() => reject(new Error('http.server 沒有在 10 秒內回報 port')), 10000);
    proc.stdout.on('data', (d) => {
      buf += d;
      const m = buf.match(/port (\d+)/);
      if (m) { clearTimeout(timer); resolve({ proc, port: Number(m[1]) }); }
    });
    proc.on('error', (e) => { clearTimeout(timer); reject(e); });
    proc.on('exit', (c) => { clearTimeout(timer); reject(new Error(`http.server 提早結束 ${c}`)); });
  });
}

(async () => {
  const { proc, port } = await serve();
  const BASE = `http://127.0.0.1:${port}`;
  const browser = await chromium.launch({ args: ['--autoplay-policy=no-user-gesture-required'] });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on('console', m => m.type() === 'error' && errors.push(m.text()));
  page.on('pageerror', e => errors.push(String(e)));

  try {
    await page.goto(`${BASE}/music.html`, { waitUntil: 'load' });
    await page.waitForFunction(() => document.querySelectorAll('#lines li').length > 0);

    const lrcLines = await page.$$eval('#lines li', els => els.map(e => e.textContent));
    check('歌詞行數 31', lrcLines.length === 31, `實際 ${lrcLines.length}`);

    for (const [t, want] of SAMPLES) {
      const got = await page.evaluate((t) => {
        paintLyrics(t);
        const on = document.querySelector('#lines li.on');
        return on ? on.textContent : null;
      }, t);
      check(`${t}s → ${want === null ? '(無)' : want}`, got === want, got === want ? '' : `亮的是「${got}」`);
    }

    /* 真的播得動:按下播放鈕之後時間要往前走 */
    await page.click('#play');
    await page.waitForTimeout(1500);
    const played = await page.evaluate(() => ({ t: au.currentTime, paused: au.paused }));
    check('按播放後時間前進', !played.paused && played.t > 0.3, `currentTime=${played.t.toFixed(2)}`);

    /* 亮的那行要被捲到視窗中線附近 —— 只驗「有沒有亮」不夠,捲錯了讀者看不到 */
    // 停掉 rAF 迴圈,否則它每一幀都用 currentTime(=0) 把高亮洗掉
    await page.evaluate(() => { window.requestAnimationFrame = () => 0; });
    await page.waitForTimeout(100);
    await page.evaluate(() => paintLyrics(95));
    await page.waitForTimeout(700);              // 捲動有 .45s 過場,量太早會量到起點
    const off = await page.evaluate(() => {
      const box = document.getElementById('lyrics').getBoundingClientRect();
      const r = document.querySelector('#lines li.on').getBoundingClientRect();
      return Math.abs((r.top + r.height / 2) - (box.top + box.height / 2));
    });
    check('亮的行捲到中線 ±40px', off < 40, `偏 ${off.toFixed(0)}px`);

    /* 給人看的一張:進度條停在 0:00 是因為 python http.server 不支援 Range,
       seek 會被彈回去——不是站的 bug。要驗 seek 得換支援 Range 的伺服器。 */
    await page.screenshot({ path: '/tmp/neko-music.png' });
    console.log('截圖:/tmp/neko-music.png');

    check('沒有 console 錯誤', errors.length === 0, errors.join(' | '));
  } finally {
    await browser.close();
    proc.kill();
  }

  const bad = results.filter(r => !r.ok);
  console.log(`\n${results.length - bad.length}/${results.length} 通過`);
  process.exit(bad.length ? 1 : 0);
})();
