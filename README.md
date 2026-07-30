# 轉生成貓貓的我們

四位深夜加班的工程師，被螢幕裡浮現的魔法陣吸進異世界，醒來全變成了貓。

線上閱讀：<https://yazelin.github.io/neko-tensei/>

## 誕生故事

2026-07-30，LINE 的 C# 社群裡一場閒聊。聊著聊著，群友的暱稱一個個變成了角色，AI「擎添助理」把這些哏畫成了漫畫，於是有了這部作品。

第二話的封面由社群裡的荒坂小次郎親手畫成——交稿之後大家才發現，那隻紅眼睛的魔王貓就是他自己。

- 點子與哏：LINE C# 社群群友
- 第二話封面：荒坂小次郎
- 內頁作畫：擎添助理（AI）
- 網站：林亞澤

## 角色

| 角色 | 職業 | 前世 |
|---|---|---|
| 小鳥不啾 | 大法師 | 眼鏡女工程師 |
| 小白++ | 劍士 | 必勝頭帶熱血菜鳥 |
| 中年攻城屍 | 武士 | 資深工程師大叔 |
| 里歐 | 盜賊 | 冷靜的咖啡系帥哥 |
| 荒坂小次郎 | 魔王 | 不明 |

## 話數

| 話 | 標題 |
|---|---|
| 第一話 | 我們怎麼變成貓了？！ |
| 第二話 | 魔力不足，得加 Token！ |

## 結構

```
episodes.json         單一事實來源:話數、頁次、alt、掛名、角色清單
build.py              產生 ep*.html、首頁話數列表、sitemap.xml、sw.js 快取清單
index.html            首頁(最新一話、話數列表、角色、誕生故事)
ep*.html              各話閱讀頁(產生檔,別手改)
char-*.html           角色介紹頁(手寫)
partials/footer.html  各頁共用的 footer 與推廣三件套
images/epN/           第 N 話的漫畫頁(webp,對白已在圖裡)
images/char-*.webp    角色對照圖
story/                分鏡與創作規範 → 見 story/README.md
manifest.json sw.js   PWA:可安裝、離線閱讀(SHELL/ASSET 兩層快取)
```

## 新增一話

1. 照 [`story/README.md`](story/README.md) 寫分鏡（對白逐字寫進 prompt）、生圖、逐頁驗字，成品進 `images/epN/`
2. `episodes.json` 加一段（頁次與 alt 都寫在這裡）
3. `python3 build.py`
4. bump `sw.js` 的 `SHELL` / `ASSET` 版本號，commit push

`build.py` 會同步首頁列表、上一話／下一話、sitemap 與離線快取清單，這幾個地方都不用手改。

## 授權

圖文內容採 [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/deed.zh-hant) 授權．林亞澤與 LINE C# 社群群友。
