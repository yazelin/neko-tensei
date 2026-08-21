# 轉生成貓貓的我們

四位深夜加班的工程師，被螢幕裡浮現的魔法陣吸進異世界，醒來全變成了貓。

線上閱讀：<https://yazelin.github.io/neko-tensei/>

## 誕生故事

2026-07-30，[LINE 的 C# 社群](https://line.me/ti/g2/PmukABqgPFrk7tMm8qt3AtHyvtNPY4dVd1HRXw)裡一場閒聊。聊著聊著，群友的暱稱一個個變成了角色。我把這些哏講給 AI「[擎添助理](https://ai.ching-tech.com/ctos-lite)」聽、請它畫成漫畫原畫初稿，再貼回群裡分享，於是有了這部作品。

後續由 Claude 搭配 gpt-image-2 接手：做成可離線閱讀的 PWA 網站、補上角色頁，並生成第二話的內容。

第二話的封面由社群裡的荒坂小次郎親手畫成——交稿之後大家才發現，那隻紅眼睛的魔王貓就是他自己。

- 點子與哏：[LINE C# 社群](https://line.me/ti/g2/PmukABqgPFrk7tMm8qt3AtHyvtNPY4dVd1HRXw)群友
- 原畫初稿：[擎添助理](https://ai.ching-tech.com/ctos-lite)（AI）
- 第二話封面：荒坂小次郎
- 網站、角色頁、第二話內容：Claude × gpt-image-2
- 統籌與拍板：林亞澤

## 角色

| 角色 | 職業 | 前世 |
|---|---|---|
| 小鳥不啾 | 大法師 | 眼鏡女工程師 |
| 小白++ | 劍士 | 必勝頭帶熱血菜鳥 |
| 中年攻城屍 | 武士 | 資深工程師大叔 |
| 里歐 | 盜賊 | 冷靜的咖啡系帥哥 |
| 荒坂小次郎 | 魔王 | 不明 |

## 想一起畫？

看 [CONTRIBUTING.md](CONTRIBUTING.md)——投一張圖、畫一整話、加新角色，三條路各自寫清楚了。

只是想許願劇情的話，直接到[首頁的許願串](https://yazelin.github.io/neko-tensei/#wish)留言就好。

## 話數

| 話 | 標題 |
|---|---|
| 第一話 | 我們怎麼變成貓了？！ |
| 第二話 | 魔力不足，得加 Token！ |

## 結構

```
index.html            首頁(最新一話、話數列表、角色、誕生故事)
music.html            主題曲播放器(動態歌詞,獨立一頁)
episodes.json         單一事實來源:話數、頁次、alt、掛名、角色清單
build.py              產生 ep/*.html、首頁話數列表、sitemap.xml、sw.js 快取清單
style.css app.js      全站樣式與行動版行為
manifest.json sw.js   PWA:可安裝、離線閱讀(SHELL/ASSET 兩層快取)
ep/N.html             各話閱讀頁(產生檔,別手改)
char/<slug>.html      角色介紹頁(手寫)
assets/               icon、favicon、og 圖、主題曲 mp3 與 LRC
images/epN/           第 N 話的漫畫頁(webp,對白已在圖裡)
images/char-*.webp    角色對照圖
partials/footer.html  各頁共用的 footer 與推廣三件套
story/                分鏡與創作規範 → 見 story/README.md
scripts/              驗收腳本
docs/superpowers/     設計與實作計劃
```

`sw.js`、`manifest.json`、`robots.txt`、`sitemap.xml`、`index.html` 必須留在根目錄——
service worker 的 scope 與各自的慣例都要求如此。

## 主題曲

〈貓貓進行曲〉在 [music.html](https://yazelin.github.io/neko-tensei/music.html)，獨立一頁的播放器：封面、逐行高亮的動態歌詞，加上一整塊 canvas 特效層（繞著封面的頻譜環、踩到拍子就往外擴的衝擊波、會被滑鼠推開的貓掌粒子）。

直播用的幾件事：

- **點畫面**炸出一把貓掌，**按住拖曳**一路灑；滑鼠移動時封面會跟著轉一點角度，背景往反方向推
- **播放中滑鼠停 2.6 秒**，上排連結與播放列自動淡出、游標也藏起來，畫面只剩封面、歌詞與特效，適合直接推進 OBS
- 空白鍵播放暫停、左右鍵 ±5 秒、`F` 全螢幕；點封面也是播放暫停；點歌詞任一行跳到那一句
- 手機不接 Web Audio（Android 關螢幕會掛起 AudioContext 直接斷音），特效改吃量出來的節拍網格：161.5 BPM、第一拍 0.02 秒，那組數字對過 200 組隨機網格的負控制

| 檔案 | 內容 |
|---|---|
| `assets/theme-song.mp3` | 音檔，ID3 帶封面與 LRC（USLT 幀，匯進支援的播放器就有動態歌詞） |
| `assets/theme-song.lrc` | 時間軸正本，網頁讀的是這一份 |
| `images/theme-song-cover.webp` | 頁面用的封面 |

時間軸怎麼來的：whisper `large-v3-turbo --max-len 1` 拿逐字時間戳，用 `SequenceMatcher` 對到歌詞（**只取時間，文字一律用歌詞正本**），再逐段對錨修正。LRC 比歌詞單多四行「喵喵喵 貓貓進行曲」：第一段副歌之後那段 hook 真的有唱，歌詞單沒寫。

**哪一行早了晚了就改 `assets/theme-song.lrc`**，純文字，改完跑驗收：

```bash
NODE_PATH=$(npm root -g) node scripts/verify-music.js
```

mp3 有 3.5 MB，**沒有進離線快取**：`sw.js` 對 `.mp3` 直接放行，讓瀏覽器自己跟伺服器談 Range，進度條拖曳才準，回訪讀者也不會白吃這些流量。

## 新增一話

1. 照 [`story/README.md`](story/README.md) 寫分鏡（對白逐字寫進 prompt）、生圖、逐頁驗字，成品進 `images/epN/`
2. `episodes.json` 加一段（頁次與 alt 都寫在這裡）
3. `python3 build.py`
4. commit push

`build.py` 會同步首頁列表、上一話／下一話、sitemap、離線快取清單與 `sw.js` 的兩個快取版號，這幾個地方都不用手改。版號是清單內容的 hash，改殼檔或換圖才會變，不必也不要手動 bump。

## 想 fork 一份畫自己的漫畫

換掉三個地方就是你自己的連載：`story/cast.json`（角色、設定圖、識別特徵、道具）、
`story/README.md`（你這部作品的鐵律）、`episodes.json`（清空，從第一話開始）。

`scripts/next_episode.py` 跟 `.github/workflows/next-episode.yml` 不用動，換後端靠環境變數：

| 環境變數 | 預設 | 說明 |
|---|---|---|
| `PLANNER_PROVIDER` | `gemini` | 寫劇本走誰。`gemini` / `openai` |
| `GEMINI_WEB_BASE_URL` | 我的自架中繼 | 設成 `https://generativelanguage.googleapis.com` 就是 Google 官方端點 |
| `GEMINI_API_KEY` | 無 | 上面那條的金鑰 |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | 任何 OpenAI 相容端點：Groq、Ollama、OpenRouter |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | 無 / `gpt-4o-mini` | 同上 |
| `OPENAI_MAX_TOKENS` | `32768` | 輸出上限。**別設小**，見下面那張表 |
| `IMAGE_PROVIDER` | `codex` | 出圖走誰。`codex`（我自架的 codex-image-service）/ `gemini` |
| `GEMINI_IMAGE_KEY` | 退回 `GEMINI_API_KEY` | 出圖用的金鑰，可以跟企劃那把分開 |
| `GEMINI_IMAGE_MODEL` | `gemini-3.1-flash-image-preview` | 影像模型 id |

**出圖端沒有 gemini-web 這個選項**：它的 `/api/edit` 只吃一張參考圖，而這條產線一頁最多
要傳 8 張（畫風錨 ＋ 道具/場景 ＋ 每個出場角色）。少了參考圖，角色一定漂。

實測（2026-08-01，同一份 prompt，企劃都通過驗證器）：

| 端點 / 模型 | 耗時 | 產出 token | 結果 |
|---|---|---|---|
| Groq `openai/gpt-oss-120b` | 7 秒 | 3865 | 六頁，通過 |
| Groq `llama-3.3-70b-versatile` | 4 秒 | — | 六頁，通過 |
| Groq `qwen/qwen3.6-27b` | 12 秒 | — | 六頁，通過 |
| llmshare `glm-5.2` | 76 秒 | 11179 | 六頁，通過 |

**輸出上限是最容易踩的坑。** Groq 不設 `max_tokens` 時預設只給 3072，企劃寫到一半
就被切斷（`finish_reason=length`），而半截 JSON 解析失敗的錯誤訊息跟真正的原因差很遠。
推理模型更凶：glm-5.2 的思考過程也吃這份額度，16384 全燒光還沒寫完，要 11000 以上的
實際產出才收得了尾。所以預設值訂 32768，腳本也會在被切斷時直接點名 `OPENAI_MAX_TOKENS`。

另一個坑：**Groq 擋在 Cloudflare 後面，看到 Python 的預設 User-Agent 直接回 403
（error code 1010）**，而回應裡沒有一個字提到 UA。腳本固定帶自己的 UA，所以不會撞到。

出圖端兩條都實測過了（2026-08-01，同一份企劃的第 02 頁，7 張參考圖）：

| 後端 | 一頁耗時 | 產出 |
|---|---|---|
| `codex`（我自架） | 234～696 秒 | 1024×1536 |
| `gemini`（官方 API） | 25 秒 | 2K 生成、落檔縮到 1024 寬 |

**`imageConfig` 一定要給。** 實測不給任何設定時，Gemini 回的是 1408×768 的**橫幅**，
一頁三格的直式分鏡直接毀掉；`aspectRatio=2:3` 才是直式，再加 `imageSize=2K` 才夠對白銳利。
prompt 裡雖然寫了 portrait 2:3，但那只是「有時候會聽」，不能當設定用。腳本已經寫死這兩個值。

品質上兩條都需要人工驗收，錯的方式也一樣：那次實測 Gemini 漏掉了法杖上的鳥、
把該出場的小白++ 換成了中年攻城屍、背景的假程式碼是一片糊掉的亂碼（畫面描述沒寫死字面時
就會這樣）。所以 PR 的逐頁對照不是裝飾，是這條產線唯一的品管。

先跑 `python3 scripts/next_episode.py --plan-only /tmp/plan.json` 只出企劃不出圖，
確認後端接通了再花出圖的錢。

**在 GitHub Actions 上換後端**：金鑰放 repo 的 Secrets（`GEMINI_API_KEY`、`OPENAI_API_KEY`、
`CODEX_IMAGE_KEY`、`GEMINI_IMAGE_KEY`），選哪個後端與模型名放 Variables（`PLANNER_PROVIDER`、
`IMAGE_PROVIDER`、`OPENAI_BASE_URL`、`OPENAI_MODEL`、`GEMINI_IMAGE_MODEL` 等）。
workflow 會照選到的組合檢查金鑰，只缺你真正用得到的那把才擋。

```bash
gh secret set GEMINI_IMAGE_KEY          # 貼上 AI Studio 金鑰
gh variable set IMAGE_PROVIDER --body gemini
```

## 授權

兩份授權，分開看：

- **圖文內容**（漫畫頁、角色圖、劇本與站上文案）採 [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/deed.zh-hant)．林亞澤與 [LINE C# 社群](https://line.me/ti/g2/PmukABqgPFrk7tMm8qt3AtHyvtNPY4dVd1HRXw)群友。見 [LICENSE](LICENSE)。
- **程式碼**（`build.py`、`scripts/`、workflow、樣板、CSS/JS）採 MIT．林亞澤。見 [LICENSE-CODE](LICENSE-CODE)。想拿這條產線去畫你自己的漫畫，隨便拿。
