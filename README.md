# 轉生成貓貓的我們

四位深夜加班的工程師，被螢幕裡浮現的魔法陣吸進異世界，醒來全變成了貓。

線上閱讀：<https://yazelin.github.io/neko-tensei/>

## 誕生故事

2026-07-30，LINE 的 C# 社群裡一場閒聊。聊著聊著，群友的暱稱一個個變成了角色，AI「擎添助理」把這些哏畫成了漫畫，於是有了這部作品。

- 點子與哏：LINE C# 社群群友
- 作畫：擎添助理（AI）
- 網站：林亞澤

## 角色

| 角色 | 職業 | 前世 |
|---|---|---|
| 小鳥不啾 | 大法師 | 眼鏡女工程師 |
| 小白++ | 劍士 | 必勝頭帶熱血菜鳥 |
| 中年攻城屍 | 武士 | 資深工程師大叔 |
| 里歐 | 盜賊 | 冷靜的咖啡系帥哥 |

## 結構

```
index.html          首頁（話數列表、角色、誕生故事）
ep1.html            第一話閱讀頁
char-*.html         角色介紹頁（每位主角一頁）
images/             漫畫頁（00-cover、01–07）與角色對照圖（char-*.jpg）
manifest.json sw.js PWA：可安裝、離線閱讀（SHELL/ASSET 兩層快取）
```

新增一話的步驟：漫畫頁放進 `images/`、開 `ep2.html`、首頁話數列表加一列、`sitemap.xml` 加網址、`sw.js` 的 `WARM` 加檔案並 bump `SHELL` 版本。

## 授權

圖文內容採 [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/deed.zh-hant) 授權．林亞澤與 LINE C# 社群群友。
