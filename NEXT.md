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

**要 yazelin 做的三件事：**

1. 設 repo secrets（`gh secret set <NAME>`）——目前 `gh secret list` 是空的：
   - `GEMINI_API_KEY`、`GEMINI_WEB_BASE_URL`（gemini-web 發的金鑰，本機拿不到，
     跟 catime 用的是同一組）
   - `CODEX_IMAGE_KEY`、`CODEX_IMAGE_BASE_URL`（跟 catime 同名同值）
2. 到 Actions 頁面手動跑一次「下一話」，看 PR 的樣子與手機可讀性。
   **`workflow_dispatch` 只認得出 default branch 上的 workflow**，所以這條 PR
   要先 merge 進 `main`，Actions 頁面才看得到「下一話」這個按鈕
3. 滿意之後把 workflow 裡 `schedule:` 那三行的註解拿掉，cron 才會開始跑

**本機怎麼試：**

先裝唯一的相依（Ubuntu 24.04 需要 `--break-system-packages`）：

```bash
pip install --user --break-system-packages opencc-python-reimplemented
```

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

- [ ] `sw.js` 的 `ASSET` 版號規則可以在 git 層自動化：`images/` 無異動時 `ASSET` 必須與 base 相同，有異動才准 bump。這次差點讓回訪讀者白抓 10.6 MB——`activate` 會刪掉舊 asset 快取，`warm()` 再用 `cache:'reload'` 整包重抓
- [ ] `app.js` 的 `deferred.userChoice` 沒有 `.catch()`，reject 時第四格標籤會卡在「安裝」
- [ ] `scripts/verify-mobile.js` 的 `freePort()` 有 TOCTOU 窗口（listen(0) → close → spawn 之間 port 可能被搶）。失敗會大聲報錯不會靜默驗錯站，可接受
- [ ] `app.js` 從 hash 跳轉時掛的 `load` 監聽器實務上是 dead code——`<img>` 有 `width`/`height`，瀏覽器會先用 aspect-ratio 保留高度。留著無害，但別誤以為它被驗過

## 驗收怎麼跑

```bash
NODE_PATH=$(npm root -g) node scripts/verify-mobile.js
```

用全域的 playwright 跑 iPhone 13 實尺寸，自己起本機靜態伺服器，驗 DOM 與座標。目前 34 項。

**注意**：safe-area 的檢查靠 `page.addInitScript()` 注入假的 inset 值——Chromium 的 device emulation 不模擬 `env(safe-area-inset-*)`，一律回 0，不注入就等於沒驗。進度條被撐成一片色塊那個 bug 就是被這個盲點放過去的。
