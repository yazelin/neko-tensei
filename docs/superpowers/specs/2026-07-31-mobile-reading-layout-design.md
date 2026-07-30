# 行動版閱讀體驗設計

2026-07-31．neko-tensei

## 要解決的問題

使用場景是**通勤時在手機上看最新一話**。目前的站在這個場景下有四個卡點：

1. 閱讀頁的頂欄跟著內容捲走，捲到一半想回首頁得往回捲
2. 一話 7 張 1024×1536 的圖，在手機上約 4000px 的捲動，沒有任何進度指示
3. 想跳下一話得一路捲到最底部
4. 關掉再打開會回到頁首，讀到哪要自己找

參考 catime 的行動版做法：手機斷點下加一條 `position:fixed` 的底部 tabbar，桌機的浮動按鈕全隱藏，用 CSS 變數同步 tabbar 高度讓內容 padding 對齊，底部吃 `env(safe-area-inset-bottom)`。

## 決策

- 閱讀頁走**沉浸式**：頂欄自動隱現、底部細進度條，不放 tabbar
- 首頁與角色頁走 **app 式**：固定底部 tabbar
- 首頁頂部加**繼續閱讀**卡

兩種頁面的工作不同，就給不同的框。閱讀頁的工作是讓畫面最大，首頁的工作是兩秒內回到上次停的地方。

## 閱讀頁（`ep*.html`）

### 頂欄

改成 `position:fixed`，內容是 `‹ 返回`、話名、`≡ 話數`。

- 往下捲收起（`transform: translateY(-100%)`），往上捲滑回
- 捲動門檻 8px，避免手指微抖就閃
- 進站時顯示，捲動超過一個螢幕高度後才開始隱現邏輯

### 進度條

底部固定一條 3px，永遠在，右側顯示 `3/7`。

用 `IntersectionObserver` 判斷目前在第幾張圖，**不要算捲動百分比**——`.credit` 與 `.reader-nav` 會讓百分比失真。每張圖掛一個 observer，進入視窗中線時更新目前頁碼。

### 版面

- `.reader` 在手機斷點拿掉 `max-width:720px`，圖片滿版
- 圖間距 6px → 2px，去掉 `border-radius`，要的是連續感
- 桌機維持現狀

### 保留

頁尾的 `.reader-nav`（回首頁／上一話／下一話）保留，只是不再是唯一出口。

## 首頁與角色頁

### 底部 tabbar

四格：`首頁`／`話數`／`角色`／`安裝`。前三個是頁內 anchor 捲動，第四個接現有的 `beforeinstallprompt`。

**第四格是條件式的**：`beforeinstallprompt` 沒觸發時（iOS Safari 永遠不會觸發）改顯示「關於」，跳到誕生故事。不做一個在 iPhone 上按了沒反應的按鈕。

高度用 CSS 變數 `--tabbar-h`，由 JS 從實際高度（含 safe-area）量出來寫進 `:root`，內容的 `padding-bottom` 跟著算。這是 catime 已經驗過的做法，直接沿用。

### 繼續閱讀卡

首頁最上方，顯示「繼續閱讀 第二話 · 第 3 頁」，點下去跳回那一張圖（`ep2.html#p3`，閱讀頁讀 hash 後 `scrollIntoView`）。

這需要 `build.py` 在產生閱讀頁時替每張圖加上 `id="pN"`（`p0` 是封面）。目前沒有，要一起改。

**沒有紀錄時整張卡不出現**——不佔位、不顯示假資料。

## 進度儲存

`localStorage` 單一 key：

```js
localStorage.setItem('nt-progress', JSON.stringify({ ep: 2, page: 3, at: Date.now() }))
```

閱讀頁捲動時節流寫入（每 500ms 最多一次）。

**這裡有個坑**：`yazelin.github.io` 是所有 Pages 專案共用的 origin，localStorage 是同一份。key 一律 `nt-` 前綴（現有的 `nt-install` 已經是這個規矩），不能用 `progress` 這種通名，否則會跟別的專案互相覆蓋。

## 不做的事

- 不做左右翻頁與橫向模式——這是直式條漫，垂直捲動就是對的
- 不做點擊螢幕左右半邊翻頁的手勢
- 不做閱讀設定（亮度、間距、字級）
- tabbar 不放「最新一話」分頁，繼續閱讀卡已經涵蓋

## 驗收

用 Playwright 的 `devices['iPhone 13']` ＋ `channel: 'chrome'` 實機尺寸驗四件事：

1. 往下捲頂欄收起、往上捲滑回
2. 進度條的頁碼與實際看到的那張圖一致
3. tabbar 沒被 iPhone 底部的 home indicator 蓋住
4. 繼續閱讀卡點下去，落在正確的那張圖

第 2 與第 4 項要用像素或 DOM 位置驗，不能只看截圖像不像。
