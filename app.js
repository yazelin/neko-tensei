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
  /* 非負整數(話數、頁碼共用)。字串、小數、NaN、負數一律不算。 */
  function isIndex(v) {
    return typeof v === 'number' && isFinite(v) && v >= 0 && Math.floor(v) === v;
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

    // 從首頁的「繼續閱讀」跳進來:圖是 lazy 的,等它有高度再捲
    if (location.hash) {
      var target = document.getElementById(location.hash.slice(1));
      if (target) {
        requestAnimationFrame(function () { target.scrollIntoView(); });
        target.addEventListener('load', function () { target.scrollIntoView(); }, { once: true });
      }
    }
  }

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
    var deferred = null;

    // 單一 handler,靠 deferred 有沒有值分支。不要用 addEventListener 再疊 onclick,
    // 那會讓「安裝」按下去同時觸發「關於」的跳轉。
    function labelAbout() { slot.innerHTML = IC.info + '<span>關於</span>'; }

    slot.addEventListener('click', function () {
      if (deferred) {
        deferred.prompt();
        // 不管裝了還是按「以後再說」,這個 event 都不能再用第二次,
        // 標籤要一起還原——否則按取消之後再點同一格會被丟去誕生故事,
        // 而 beforeinstallprompt 同一次瀏覽不會再觸發,錯到重新載入為止。
        deferred.userChoice.then(function () { deferred = null; labelAbout(); });
      } else {
        // 誕生故事只在首頁,用相對路徑,角色頁按下去才不會是死連結
        location.href = './#origin';
      }
    });

    window.addEventListener('beforeinstallprompt', function (e) {
      e.preventDefault();
      deferred = e;
      slot.innerHTML = IC.down + '<span>安裝</span>';
    });

    function measure() {
      document.documentElement.style.setProperty('--tabbar-h', nav.offsetHeight + 'px');
    }
    measure();
    window.addEventListener('resize', measure);

    // 繼續閱讀只在首頁。角色頁也有 .hero,不能只靠它判斷,
    // 沒有紀錄也整張不出現,不佔位也不顯示假資料
    var prog = readProgress();
    var hero = document.querySelector('.hero');
    if (!prog || !hero || !document.body.hasAttribute('data-home')) return;

    // nt-progress 不能當可信輸入:yazelin.github.io 是所有 Pages 專案共用的
    // origin,同 origin 的別的專案寫得進這個 key。話數要真的存在(首頁列表上
    // 有對應的 epN.html 連結才算),頁碼要是非負整數,文字一律 textContent。
    var ep = prog.ep, page = prog.page;
    if (!isIndex(ep) || ep < 1 || !isIndex(page)) return;
    if (!document.querySelector('a[href="ep' + ep + '.html"]')) return;

    var CN = ['', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十'];
    var where = page === 0 ? '封面' : '第 ' + page + ' 頁';
    var card = document.createElement('a');
    card.className = 'resume';
    card.href = 'ep' + ep + '.html#p' + page;

    var ic = document.createElement('span');
    ic.className = 'resume-ic';
    ic.setAttribute('aria-hidden', 'true');
    ic.textContent = '▶';

    var txt = document.createElement('span');
    txt.className = 'resume-t';
    txt.appendChild(document.createTextNode('繼續閱讀'));
    var sub = document.createElement('small');
    sub.textContent = '第' + (CN[ep] || ep) + '話 · ' + where;
    txt.appendChild(sub);

    card.appendChild(ic);
    card.appendChild(txt);
    hero.insertAdjacentElement('afterbegin', card);
  }


  /* 討論區(giscus)。捲到附近才載入——第三方 iframe 不該讓通勤讀者一進站就付流量。
     設定放在 HTML 的 #giscus 佔位元素上,這支只負責在對的時機把 script 塞進去。
     只帶 data-category-id 不帶 data-category:分類 id 才是 giscus 實際比對的欄位,
     這樣之後在 GitHub 上把分類改成中文名也不會壞。 */
  function initGiscus() {
    var el = document.getElementById('giscus');
    if (!el || !('IntersectionObserver' in window)) return;
    var loaded = false;
    var io = new IntersectionObserver(function (entries) {
      if (loaded) return;
      var near = entries.some(function (e) { return e.isIntersecting; });
      if (!near) return;
      loaded = true;
      io.disconnect();
      var s = document.createElement('script');
      s.src = 'https://giscus.app/client.js';
      s.async = true;
      s.crossOrigin = 'anonymous';
      s.setAttribute('data-repo', 'yazelin/neko-tensei');
      s.setAttribute('data-repo-id', 'R_kgDOToGp7w');
      s.setAttribute('data-category-id', el.dataset.categoryId);
      s.setAttribute('data-mapping', el.dataset.mapping);
      if (el.dataset.term) s.setAttribute('data-term', el.dataset.term);
      s.setAttribute('data-strict', '1');
      s.setAttribute('data-reactions-enabled', '1');
      s.setAttribute('data-emit-metadata', '0');
      s.setAttribute('data-input-position', 'top');
      s.setAttribute('data-theme', 'dark_dimmed');
      s.setAttribute('data-lang', 'zh-TW');
      s.setAttribute('data-loading', 'lazy');
      el.appendChild(s);
    }, { rootMargin: '300px' });
    io.observe(el);
  }

  function boot() {
    var reader = document.querySelector('main.reader');
    if (reader) initReader(reader);
    else initShell();
    initGiscus();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
