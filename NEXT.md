# 下一步

## 討論區（下一個要做的）

設計已定，順序排在 pipeline 前面，這樣 pipeline 上線時就有社群許願可以讀。

- [ ] 開 GitHub Discussions——`gh api repos/yazelin/neko-tensei --jq .has_discussions` 目前是 `false`
- [ ] 開兩個分類：`劇情許願`（首頁一串，giscus `data-mapping="specific"` 配固定 term）、`每話討論`（`ep*.html` 各一串，`data-mapping="pathname"`）
- [ ] 掛 giscus，做法照 `catime/docs/index.html` 的 lazy-load 版本改 repo 名
- [ ] **這步要 yazelin 本人做**：到 github.com 授權 giscus app，我沒有權限
- [ ] 抓 `data-repo-id` 與 `data-category-id`（`gh api graphql` 查得到）

## 自動連載 pipeline

設計在 `docs/superpowers/specs/2026-07-31-auto-episode-pipeline-design.md`，還沒寫實作計劃。等討論區上線後再做，才有許願可以讀。

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
