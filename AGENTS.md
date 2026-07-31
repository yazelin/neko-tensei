# 給協作的 AI 與人

這份是索引與地雷圖，不重複既有文件。動手前先讀完這一頁。

**創作規則的正本在 [`story/README.md`](story/README.md)**，畫新一話一定要先讀它。這裡只放「不知道就會做錯、而且錯了很安靜」的東西。

---

## 生圖時角色會跑偏——解法

**先講最重要的一句：要傳參考圖。** 只把文字 prompt 丟給生圖工具，角色一定會漂——金牌上的字不見、憑空多一頂帽子、前世人形整組畫錯。這不是 prompt 寫得不夠詳細的問題，文字描述本身就不夠。

而且你的生圖後端**必須支援多張參考圖的 image-edit 模式**。純文字生圖（text-to-image）用不了這套做法。

做法已經包成技能：[cast-lock](https://github.com/yazelin/cast-lock-skill)。這個 repo 的角色設定在 [`story/cast.json`](story/cast.json)，直接可以跑：

```bash
# 組 prompt（含參考圖清單與逐項特徵）
python3 ~/cast-lock-skill/build.py --cast story/cast.json --chars uncle,xiaobai --body panel.txt

# 只印參考圖路徑,餵給生圖工具
python3 ~/cast-lock-skill/build.py --cast story/cast.json --chars uncle,xiaobai --refs-only

# 出圖後印驗收清單,逐項對照
python3 ~/cast-lock-skill/check.py --cast story/cast.json --chars uncle,xiaobai
```

下面是這套做法背後的道理，值得讀一次再動手。

### 一定要傳角色設定圖當參考圖

`story/refs/` 底下有六張，只有貓、沒有前世、沒有文字：

```
story/refs/xiaoniao.webp   小鳥不啾
story/refs/xiaobai.webp    小白++
story/refs/uncle.webp      中年攻城屍
story/refs/leo.webp        里歐
story/refs/kojiro.webp     荒坂小次郎
story/refs/past-four.webp  四位主角的前世人形（只有畫記憶泡時才傳）
```

**參考圖第一張永遠是 `images/ep1/07.webp`**，鎖畫風、上墨感與手寫黑體字。之後才接該頁出場角色的設定圖。prompt 裡要用 `REFERENCE IMAGES:` 逐張標明哪張是誰，模型才對得上。

程式化的版本在 [`scripts/prompt.py`](scripts/prompt.py)，人工重跑與自動 pipeline 共用同一份，不要各寫一份。

### 特徵要寫到字面，不能只寫類別

| 寫這樣會漂 | 要寫這樣 |
|---|---|
| 圓形金牌 | **刻著一個「貓」字**的圓形金牌 |
| 戴眼鏡 | 圓形細金框眼鏡，**臉上一定看得到** |
| 黑色斗篷 | 黑色連帽斗篷，**上面滿是金色肉球扣** |
| 紅色紋章 | 圓形紅色紋章，**樹在爪上** |

實際踩過的坑：只寫「圓形金牌」，模型畫成肉球圖案。

### 「沒有什麼」跟「有什麼」一樣要寫死

**小白++ 貓形沒有頭帶。** 那條寫著「必勝」的白頭帶是他**前世**限定，貓形頭上是空的。不寫「bare head with NO headband and NO hat of any kind」，模型就會自己補一頂上去。

同理：荒坂小次郎沒有前世側，不能給他用內心 OS 的雲朵思考框。

### 前世永遠黑白，貓世界永遠全彩

記憶泡裡的人形一律灰階配霓虹光，貓世界全彩。這個對比是刻意的。第二話第 04 頁的記憶泡第一次生出來四個全錯（棕髮沒髮夾、頭帶沒字、壯漢變光頭胖子、金髮變黑髮）**而且全畫成彩色**，補上 `past-four.webp` 與「THE PAST IS ALWAYS BLACK AND WHITE」才修好。

### 小鳥不啾身上的鳥每次可以不一樣

法杖上一隻、頭頂一隻，但品種顏色配件每頁都可以不同。她叫小鳥不啾**不是因為她是鳥，是因為鳥會自己來停在她身上**——前世髮上那枚小鳥髮夾，轉生後變成真的。三份正典的鳥本來就長得不一樣，這條設定把不一致變成了設定本身。

### 對白跟圖一起生，不做字圖分離

對白寫進 prompt 讓模型連對話框一起畫。**不要事後用程式疊字**——疊出來的框跟畫面是兩層東西，看得出來。（這條試過，被否決了。）

代價是改一個字＝整頁重生，所以一頁的對白控制在 3～6 句、句子不要長。

### 對話框形狀要跟著情緒走

七種框型（爆炸／橢圓／弱框／抖框／雲朵思考／魔王黑底／直角旁白），逐句在 prompt 裡指定。**整頁都是圓角矩形就是錯的**——模型會這樣預設，要在 prompt 末端加一句 FINAL CHECK 壓住。

---

## 這個 repo 的地雷

### `ep/*.html` 是產生檔，改它等於白改

由 `build.py` 從 `episodes.json` 產生。要改就改 `build.py` 或 `episodes.json`，然後跑：

```bash
python3 build.py
```

`index.html` 的話數列表、`sitemap.xml`、`sw.js` 的快取清單也都是它產的（在標記註解之間）。

### `sw.js` 的 `ASSET` 只有換圖才能 bump

```js
const SHELL = 'nt-shell-vN';   // 每次部署都 bump
const ASSET = 'nt-asset-vN';   // 只有同名檔換內容才 bump
```

跟著 `SHELL` 一起 bump 會讓 `activate` 刪掉舊 asset 快取，`warm()` 再用 `cache:'reload'` 整包重抓約 **10.6 MB**。讀者在捷運上開站會白吃這些流量。

### localStorage 的 key 一律 `nt-` 前綴

`yazelin.github.io` 是**所有 GitHub Pages 專案共用的 origin**。用 `progress` 這種通名會跟別的專案互相覆蓋。同理，從別的專案寫進來的資料不可信——`app.js` 讀 `nt-progress` 時有驗證欄位型別、用 `textContent` 不用 `innerHTML`。

### 簡繁檢查不要自己造字表

pipeline 的驗證器換過三次做法，前兩次都是被「拿既有真實內容當回歸測試」打掉的：

| 做法 | 為什麼壞 |
|---|---|
| 手打 231 字的簡體字表 | 混進正體字（`那`、`只`、`巨`、`唯`、`反`、`埋`、`准`），「那」幾乎每句話都有 |
| `OpenCC('s2t')` 往返比對 | 把「吃」轉成「喫」（古字），第一話「吃我一發」被誤判 |
| `STCharacters.txt` 字元比對 | 誤殺 `群`、`秘`、`床`、`峰`、`痴`、`灶`、`粽`，而「群」就在 repo 自己的文案裡（「LINE C# 社群」） |

現在的版本再加 `TWVariants.txt` 過濾與一份**只放行不封鎖**的例外表。細節見 `scripts/next_episode.py` 的 `has_simplified()`。

---

## 寫測試的紀律

這個專案的審查抓到過**七次**假陽性測試，根因每次都一樣：

> **斷言的字串同時存在於多個來源，所以被測的邏輯壞掉了，測試照樣綠。**

實例：斷言 `FORMER HUMAN SELVES` 驗「有沒有帶前世設定」，但 `REF['past']` 的說明文字本身就含那串；斷言 `SHOUT` 驗「prompt 有沒有列出七種框型」，但 `story/README.md` 的框型表裡就有。

**規矩：**

1. 挑斷言字串前先 `grep -rn` 全 repo，確認它**只有一個來源**
2. 不確定就斷言**那個常數本身**，不要斷言組合後的整份字串
3. 每寫一條測試，問一次：「把我要驗的那行邏輯拿掉，這條還會過嗎？」會的話它是假的
4. **拿既有的真實內容當回歸測試**——這條連續抓到三個版本的簡繁檢查錯誤
5. 做 mutation 驗證時用 `python3 -B` 或先清 `scripts/__pycache__`，同尺寸的改動會重用舊 bytecode 給你假結果

---

## 驗收怎麼跑

```bash
# 行動版體驗（42 項，iPhone 13 實尺寸，驗 DOM 與座標不是看截圖）
NODE_PATH=$(npm root -g) node scripts/verify-mobile.js

# pipeline 單元測試
python3 -B -m unittest discover -s scripts -p 'test_*.py'
```

行動版驗收的 safe-area 檢查靠 `page.addInitScript()` 注入假的 inset 值——Chromium 的 device emulation 不模擬 `env(safe-area-inset-*)`，一律回 0，不注入就等於沒驗。

沒有 `package.json`（playwright 用全域的），只有一個 pip 相依 `opencc-python-reimplemented`。**不要新增相依。**

---

## 文件在哪

| 檔案 | 內容 |
|---|---|
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | 協作手冊：投一張圖／畫一整話／加新角色，三條路的完整步驟 |
| [`story/cast.json`](story/cast.json) | 角色設定的機器可讀版本，給 [cast-lock](https://github.com/yazelin/cast-lock-skill) 用 |
| [`story/README.md`](story/README.md) | 創作規範正本：分工、鐵律、角色特徵、框型表 |
| `story/epN.md` | 每一話的逐頁分鏡與生圖 prompt |
| [`NEXT.md`](NEXT.md) | 下一步與技術債 |
| `docs/superpowers/specs/` | 設計文件 |
| `docs/superpowers/plans/` | 實作計劃 |
| [`episodes.json`](episodes.json) | 話數與頁次的單一事實來源 |
