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

  function boot() {
    var reader = document.querySelector('main.reader');
    if (reader) initReader(reader);
    else initShell();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
