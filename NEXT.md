# 下一步

## 討論區（已上線 2026-07-31）

- 首頁 `#wish`：劇情許願串，內建 **Ideas** 分類，`data-mapping="specific"`、term = `劇情許願`
- 每一話：自己的討論串，內建 **General** 分類，`data-mapping="pathname"`
- giscus 捲到附近才載入（`IntersectionObserver`，`rootMargin: 300px`）

**GitHub 沒有開放用 API 建立討論分類**，所以用內建的兩個。想改成中文名可以到
`https://github.com/yazelin/neko-tensei/settings/discussions` 改，**不會壞**——
前端只帶 `data-category-id` 不帶 `data-category`，giscus 比對的是 id。

分類 id（`app.js` 與 `build.py` 各存一份）：Ideas `DIC_kwDOToGp784DCVjL`、General `DIC_kwDOToGp784DCVjJ`。

## 自動連載 pipeline（已實作，未啟用）

程式在 `scripts/next_episode.py`，workflow 在 `.github/workflows/next-episode.yml`。

分工：**企劃（文字）**與**出圖**各自可以換後端，看 `PLANNER_PROVIDER` 與
`IMAGE_PROVIDER` 兩個環境變數，預設是 gemini-web 出文字、codex-image-service 出圖。
別人 fork 要換成自己的服務時看 README 的「想 fork 一份畫自己的漫畫」那張表。

實測過的組合（2026-08-01）：企劃端 Groq（gpt-oss-120b / llama-3.3-70b / qwen3.6-27b）
與 llmshare glm-5.2 都出得了通過驗證器的六頁企劃。出圖端 `codex` 與 `gemini` 都真的打過，
Gemini 一頁 25 秒(codex 是 234～696 秒),**但 `imageConfig` 不給就會回 1408×768 的橫幅**。
金鑰用的是 .11 上 gemini-web 的 `GEMINI_OFFICIAL_API_KEY`(按張計費,測試花了 5 張)。

**要 yazelin 做的兩件事：**

（secrets 已經設好了，`gh secret list` 看得到 `GEMINI_API_KEY` 與 `CODEX_IMAGE_KEY`。
值來自 repo 外的 `/home/ct/novel-token-unlimited/漫畫/keys.json`，鍵名 `gemini-web`
與 `codex-image-service`，**不是 catime 那組**。`GEMINI_WEB_BASE_URL` 與
`CODEX_IMAGE_BASE_URL` 刻意不設，腳本內建 `https://ching-tech.ddns.net/gemini-web`
與 `.../codex-image`，只有服務搬家才需要補上去覆蓋。）

1. 到 Actions 頁面手動跑一次「下一話」，看 PR 的樣子與手機可讀性。
   **`workflow_dispatch` 只認得出 default branch 上的 workflow**，所以這條 PR
   要先 merge 進 `main`，Actions 頁面才看得到「下一話」這個按鈕
2. 滿意之後把 workflow 裡 `schedule:` 那三行的註解拿掉，cron 才會開始跑

**本機怎麼試：**

先裝兩個相依（Ubuntu 24.04 需要 `--break-system-packages`）：

```bash
pip install --user --break-system-packages opencc-python-reimplemented pillow
```

`opencc` 驗簡繁，`pillow` 落檔時把圖重壓成 webp——生圖服務回的是近無損檔，
一頁 3.7 MB，不壓一話就 23 MB，而這個站是 PWA，圖全部會被 precache。

```bash
# 金鑰只從環境變數讀,不要寫進任何檔案
export GEMINI_API_KEY=$(python3 -c "import json;print(json.load(open('/home/ct/novel-token-unlimited/漫畫/keys.json'))['gemini-web'])")

# 只出企劃,存檔,不出圖不落檔
python3 scripts/next_episode.py --plan-only /tmp/plan.json

# 用現成企劃驗證整條線的前半段
python3 scripts/next_episode.py --plan-from /tmp/plan.json --dry-run

# 跑完但不出圖(會真的寫檔,記得先開分支)
python3 scripts/next_episode.py --plan-from /tmp/plan.json --skip-images

# 單元測試
python3 -m unittest discover -s scripts -p 'test_*.py' -v
```

## 行動版留下的技術債

- [x] `sw.js` 的版號已經改成內容 hash（`build.py` 的 `digest()`）：圖沒動 `ASSET` 就不會變，殼沒動 `SHELL` 就不會變，兩種誤觸都不可能再發生。`scripts/check-sw-version.sh` 因此退休刪除，pipeline `publish()` 裡那段正則 +1 也刪了
- [ ] `app.js` 的 `deferred.userChoice` 沒有 `.catch()`，reject 時第四格標籤會卡在「安裝」
- [ ] `scripts/verify-mobile.js` 的 `freePort()` 有 TOCTOU 窗口（listen(0) → close → spawn 之間 port 可能被搶）。失敗會大聲報錯不會靜默驗錯站，可接受
- [ ] `app.js` 從 hash 跳轉時掛的 `load` 監聽器實務上是 dead code——`<img>` 有 `width`/`height`，瀏覽器會先用 aspect-ratio 保留高度。留著無害，但別誤以為它被驗過

## 驗收怎麼跑

```bash
NODE_PATH=$(npm root -g) node scripts/verify-mobile.js
```

用全域的 playwright 跑 iPhone 13 實尺寸，自己起本機靜態伺服器，驗 DOM 與座標。目前 34 項。

**注意**：safe-area 的檢查靠 `page.addInitScript()` 注入假的 inset 值——Chromium 的 device emulation 不模擬 `env(safe-area-inset-*)`，一律回 0，不注入就等於沒驗。進度條被撐成一片色塊那個 bug 就是被這個盲點放過去的。

## 視覺驗收（2026-08-06 落地，尚未接進 Actions）

**已接進 pipeline**（2026-08-06）。`scripts/verify_pages.py` 有兩條後端、同一份規則：
本機走 `codex exec`，CI 走 `.11` 的 codex-image-service `/v1/vision`（該端點就是為了
這件事加的）。金鑰用出圖那把 `CODEX_IMAGE_KEY`，workflow 本來就傳了，沒有改 workflow。
`next_episode.py` 出圖後逐頁驗，結果寫進 PR 內文的「機器驗收」段。

不走官方 Gemini API 的原因：不必另生金鑰，額度也跟出圖同一個 ChatGPT 訂閱池。
`.11` 的 gemini-web 中繼則是**不能用**——它的 Gemini 相容端點只轉文字，圖片 part
會被丟掉（回 200 但模型收不到圖）。

現況與已知邊界：

- 回歸集 13/13（`--regression`）。實測每頁 9–17 秒，一話七頁約兩分鐘。
- **抓得到**：眼鏡戴到別的角色身上、對白裡合法字組成的錯詞（「完旦」「逼」）、
  狀聲字／頁碼／簽名。
- **抓不到**：角色被畫得像另一個角色但仍分辨得出來（小白++ 被畫蓬鬆那類）。
  四種規則寫法都漏抓，這是程度問題，沒有可寫死的判準，留人工。
- **不擋落檔**：判定寫進 PR 內文給人看，人才是閘門。機器判錯而擋掉整話，比漏報
  一頁還糟——重跑一話是 36 分鐘。

## 對白框歸屬:已上線內容的普查（2026-08-06 待辦）

驗收加上「逐格對照劇本的說話者」（規則 B）之後，回歸集裡六頁上線內容同時被判
出「對白框指向的角色跟劇本不符」。ep3/01 已逐圖確認機器是對的：第 3 格
「等等，這個警示紅字……」的框指向小白++，劇本說那是里歐。

**這不是第六話才有的新問題**，只是以前沒有工具看得到。待辦：

1. 拿全部五話跑一次 `verify_pages.py --regression` 以外的普查，逐頁確認比例
2. 決定要不要回頭重生。重生一頁約 226 秒，而框的位置是生圖模型自己排的，
   重擲不保證會好——可能要先在 prompt 裡把「氣泡放在說話者附近、尾巴指向他」
   寫成硬性要求，再一起重生
