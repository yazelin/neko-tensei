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
