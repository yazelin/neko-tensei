# 自動連載 pipeline 設計

2026-07-31．neko-tensei

## 要做什麼

每週自動產出下一話的劇情、prompt 與圖，開成 PR 讓人一鍵發佈。機器沿用 catime 已經跑順的那一套：GitHub Actions cron → python 腳本 → gemini-web 出點子 → codex-image-service 出圖 → commit 進 repo → Pages 自動發佈。

## 為什麼要保留人工閘門

catime 產的是彼此無關的貓圖，錯了下一小時就洗掉。這部是有連續性的故事，掛在真實社群成員的暱稱底下，而且下一話還得接著上一話走。

第二話製作過程實際發生的漂移（都是人盯著看才抓到的）：

| 類型 | 事件 |
|---|---|
| 模型漂移 | 中年攻城屍的「貓」字金牌變成肉球圖案 |
| 模型漂移 | 小鳥不啾的眼鏡在某些格消失 |
| 模型漂移 | 第 04 頁四顆前世記憶泡全錯，且該黑白的畫成彩色 |
| 模型漂移 | 里歐「隱形只隱一半」，三次裡兩次畫成實心 |
| 模型漂移 | 對話框形狀退回全圓角矩形，發生三次 |
| 前一輪 | 第一話第 04 頁初版角色服裝跟封面對不上（`舊版/04-初版-角色飄掉.jpg`） |

**重點不是「劇情會不會偏」。** 文字劇本其實好控制——canon 餵進去，寫出接得上的劇情現在的模型做得不錯，而且文字可讀可審。

真正會偏的是**「劇本寫的」跟「圖畫出來的」之間那道縫**。里歐那格是最好的例子：分鏡寫得清清楚楚「上半身透明、下半身實心」，圖出來是一隻完整的橘貓——文字層完全正確，圖層把整頁的笑點吃掉了。去讀那話的分鏡檔案，會覺得一切正常。

所以閘門要看的不是劇情，是**這張圖有沒有照劇本畫**。這件事只能用眼睛，但只要幾秒鐘。

## 節奏

每週五台北時間 22:00（cron `0 14 * * 5`，UTC）＋ `workflow_dispatch` 手動觸發。`concurrency` 群組鎖住避免重疊。

一次產滿一話：**封面 1 張 ＋ 內頁 6 張 = 7 張**，因為劇情有完整弧線，審一次就好。

封面預設由 pipeline 產（用該話的三個轉折當構圖依據，全員入鏡）。若 `episodes.json` 該話已經填了社群投稿的封面檔名，pipeline 就跳過封面只產內頁——社群投稿永遠優先，也永遠人工放。

## 流程

一支 `scripts/next_episode.py`：

### 1. 讀 canon

- `story/README.md` — 創作規範與角色特徵表
- `story/ep*.md` — 前幾話分鏡（含伏筆）
- `episodes.json` — 已出的話、標題、日期

### 2. gemini-web 出企劃

呼叫自架的 gemini-web（`GEMINI_WEB_BASE_URL`，與 catime 同一個服務），要求回傳 JSON：

```json
{
  "title": "…",
  "desc": "…",
  "beats": ["轉折一", "轉折二", "轉折三"],
  "pages": [
    {
      "n": "01",
      "panels": [
        { "pos": "top", "scene": "…", "lines": [
            { "speaker": "xiaobai", "shape": "SHOUT", "text": "…" } ] }
      ],
      "chars": ["xiaoniao", "xiaobai"]
    }
  ]
}
```

`chars` 決定該頁要傳哪幾張 model sheet 當參考圖。

### 3. 驗企劃（純程式，不用 AI）

不過就重試一次，再不過開 issue 停下：

- 必填欄位齊全，內頁頁數為 6
- 對白不含簡體字：用 `opencc-python-reimplemented` 的 `s2t` 轉一次，轉完不等於原字串就是有簡體。不用手維護字表，邊界情況才不會漏
- 每頁的 `shape` 不能全部相同（框型必須分化）
- `shape` 只能是規範裡那七種
- 荒坂小次郎不能配 `THOUGHT`（他沒有前世側，內心 OS 手法對他不成立）
- 標題與既有話數不重複

### 4. 出圖

把目前放在 scratchpad 的 `gen.build_prompt` 搬進 repo 成 `scripts/prompt.py`，成為 pipeline 與人工重跑共用的單一來源。

逐頁打 codex-image-service（`POST /v1/images/jobs` + `reference_images_base64`），參考圖照現有規則組：image 1 固定 `images/ep1/07.webp`，後面接該頁出場角色的 `story/refs/*.webp`。

### 5. 落檔

- 圖進 `images/epN/`
- 分鏡寫 `story/epN.md`（沿用第二話的格式）
- `episodes.json` 加一段
- 跑 `python3 build.py`
- bump `sw.js` 的 `SHELL` / `ASSET` 版本

### 6. 開 PR

**不自動 merge。** PR 內文直接貼那幾張圖（GitHub 內嵌圖片，手機上滑得動），每張圖底下附一行「劇本說的」，讓人對照圖有沒有畫出來。

不另外蓋預覽站。PR 內嵌圖片在手機上就夠用，多蓋一個 preview 分支只是多一個會壞的東西。

## 失敗處理

任何一步失敗就開 issue 標 `auto-episode` 並附錯誤，**不留半成品 PR**。已產出的圖留在分支上不刪，下次可以續跑。

## 護欄

- 出圖上限 7 張（封面＋6 內頁）、重試上限 3 次
- 同時只允許一個開著的 `auto-episode` PR，沒 merge 就不產下一話（避免堆積成一疊沒人審的草稿）
- 用既有的 `CODEX_IMAGE_KEY` / `CODEX_IMAGE_BASE_URL` / `GEMINI_WEB_BASE_URL` secrets，與 catime 同名，不新增憑證

## 不做的事

- 不自動 merge
- merge 前不發 Telegram 或 FB
- 不做多線平行連載
- 不自動覆蓋社群投稿的封面（已填的封面檔名一律跳過）

## 驗收

先用 `workflow_dispatch` 手動跑一次第三話：

1. PR 有開，內文的圖在手機上滑得動
2. 每張圖底下的「劇本說的」對得上
3. 企劃驗證有真的擋東西——故意餵一份全圓角框型的企劃，確認它被擋下來並開 issue
4. 失敗路徑：故意讓出圖失敗一次，確認開了 issue 且沒有留下半成品 PR

四項都過，再打開 cron。
