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
  const missing = [];
  page.on('console', m => m.type() === 'error' && errors.push(m.text()));
  page.on('pageerror', e => errors.push(String(e)));
  page.on('response', r => { if (r.status() >= 400) missing.push(`${r.url()} ${r.status()}`); });

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

    /* 貓掌要真的往上飄:量最高那隻三秒內升了多少,不是看畫面上有沒有粒子。
       之前 vy 被每秒 90% 的衰減吃光,終端速度只剩 13px/s,貓掌只在底部蠕動。
       注意這段要跑在下面關掉 rAF 之前,不然一幀都不會前進。 */
    await page.evaluate(() => { paws.length = 0; });
    await page.waitForFunction(() => paws.length >= 3, { timeout: 8000 });
    const y0 = await page.evaluate(() => Math.min(...paws.map(p => p.y)));
    await page.waitForTimeout(3000);
    const y1 = await page.evaluate(() => Math.min(...paws.map(p => p.y)));
    check('貓掌一路往上飄', y0 - y1 > 150, `三秒升了 ${(y0 - y1).toFixed(0)}px`);

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

    /* 頻譜環有沒有真的繞著封面:在封面外緣那一圈取樣,要幾乎都畫得到;
       再往外兩倍半徑取一次當負控制,那裡應該是空的。只看截圖看不出圓心跑掉。 */
    const ring = await page.evaluate(() => {
      const c = document.getElementById('fx'), g2 = c.getContext('2d');
      const dp = c.width / innerWidth;
      const r = document.getElementById('art').getBoundingClientRect();
      const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
      const R = r.width * .76;
      const hit = (rad) => {
        let n = 0, tot = 0;
        for (let i = 0; i < 72; i++){
          const a = i / 72 * 6.283 - 1.5708;
          const x = Math.round((cx + Math.cos(a) * rad) * dp);
          const y = Math.round((cy + Math.sin(a) * rad) * dp);
          if (x < 0 || y < 0 || x >= c.width || y >= c.height) continue;
          tot++;
          if (g2.getImageData(x, y, 1, 1).data[3] > 6) n++;
        }
        return tot ? n / tot : 0;
      };
      return { on: hit(R + 2), off: hit(R * 2.5) };
    });
    check('頻譜環繞在封面外緣', ring.on > .6, `命中率 ${(ring.on * 100).toFixed(0)}%`);
    check('負控制:兩倍半徑外是空的', ring.off < .2, `命中率 ${(ring.off * 100).toFixed(0)}%`);

    /* 滑鼠互動:點一下會炸出貓掌與一圈衝擊波 */
    const before = await page.evaluate(() => paws.length);
    await page.mouse.click(300, 700);
    const after = await page.evaluate(() => ({ paws: paws.length, waves: waves.length }));
    check('點畫面炸出貓掌', after.paws - before >= 10, `多了 ${after.paws - before} 隻`);
    check('點畫面有衝擊波', after.waves >= 1, `${after.waves} 圈`);

    /* 播放中滑鼠不動,介面要自己收起來(直播畫面只留封面與歌詞) */
    await page.evaluate(() => { au.play(); wake(); });
    await page.waitForTimeout(3200);
    check('閒置後介面收起來', await page.evaluate(() => document.body.classList.contains('idle')));
    await page.evaluate(() => { au.pause(); });

    /* 游標與貓耳:路徑打錯只會安靜地退回系統箭頭,截圖也照不到游標,只能查算出來的樣式 */
    const skin = await page.evaluate(() => {
      const play = document.getElementById('play');
      return { body: getComputedStyle(document.body).cursor,
               play: getComputedStyle(play).cursor,
               idle: (() => { document.body.classList.add('idle');
                              const c = getComputedStyle(play).cursor;
                              document.body.classList.remove('idle'); return c; })() };
    });
    check('游標換成貓掌', /cursor-paw\.png/.test(skin.body), skin.body.slice(0, 48));
    check('可以點的東西是金色貓掌', /cursor-paw-gold/.test(skin.play), skin.play.slice(0, 48));
    check('閒置時連游標一起藏', skin.idle === 'none', skin.idle);
    /* 封面滑過去要浮出播放鈕,而且圖示要跟播放狀態一致(兩顆共用同一個 class) */
    const hov0 = await page.evaluate(() => getComputedStyle(document.querySelector('.art-hover')).opacity);
    await page.hover('#art');
    await page.waitForTimeout(400);
    const hov1 = await page.evaluate(() => getComputedStyle(document.querySelector('.art-hover')).opacity);
    check('封面平常不蓋東西', hov0 === '0', hov0);
    check('滑到封面浮出播放鈕', +hov1 > .9, hov1);
    const icons = await page.evaluate(async () => {
      const d = () => [...document.querySelectorAll('.picon')].map(p => p.getAttribute('d'));
      au.pause(); const stopped = d();
      await au.play(); const playing = d();
      au.pause();
      return { stopped, playing };
    });
    check('兩顆圖示都跟著狀態走',
          icons.stopped.length === 2 && new Set(icons.stopped).size === 1
          && new Set(icons.playing).size === 1 && icons.stopped[0] !== icons.playing[0],
          JSON.stringify(icons).slice(0, 90));

    check('沒有抓不到的檔案', missing.length === 0, missing.join(' | '));
    check('沒有 console 錯誤', errors.length === 0, errors.join(' | '));
  } finally {
    await browser.close();
    proc.kill();
  }

  const bad = results.filter(r => !r.ok);
  console.log(`\n${results.length - bad.length}/${results.length} 通過`);
  process.exit(bad.length ? 1 : 0);
})();
