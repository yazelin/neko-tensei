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
與 llmshare glm-5.2 都出得了通過驗證器的六頁企劃。**出圖端只實測過 codex**，
`IMAGE_PROVIDER=gemini` 那條有單元測試但還沒拿真的 AI Studio 金鑰打過。

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
