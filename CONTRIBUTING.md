# 協作手冊

想投一張圖，或想畫一整話。這份告訴你怎麼做。

先確認你要做哪一種：

| 我想做的事 | 跳到 |
|---|---|
| 投一張圖（封面、插畫、同人） | [投一張圖](#投一張圖) |
| 畫完整的一話 | [畫一整話](#畫一整話) |
| 加一個新角色 | [加新角色](#加新角色) |
| 只是想許願劇情 | [首頁的許願串](https://yazelin.github.io/neko-tensei/#wish)，不用讀這份 |

---

## 開始之前：角色為什麼會跑偏

不管你要做哪一種，先知道這件事，不然一定會撞牆。

**只給文字 prompt，AI 畫出來的角色一定會漂。** 金牌上的字不見、憑空多一頂帽子、前世的人形整組畫錯。這不是 prompt 寫得不夠詳細的問題——文字描述本身就不夠。

解法是三件事一起做：

1. **傳角色設定圖當參考圖**（`story/refs/` 底下）
2. **特徵寫到字面**——「刻著一個『貓』字的圓形金牌」不是「圓形金牌」
3. **「沒有什麼」也要寫死**——不寫「貓形沒有頭帶」，模型每次都補一頂上去

這套做法包成了技能：[cast-lock](https://github.com/yazelin/cast-lock-skill)。這個 repo 的角色設定在 [`story/cast.json`](story/cast.json)。

**你的生圖工具必須支援多張參考圖的 image-edit。** 純文字生圖（text-to-image）用不了這套方法，你只會看到角色繼續漂、找不出原因。

### 裝技能

**最簡單的方式：不用裝。** 這兩支腳本是純 Python 3 標準函式庫，clone 下來直接跑就好：

```bash
git clone https://github.com/yazelin/cast-lock-skill ~/cast-lock-skill
python3 ~/cast-lock-skill/build.py --help
```

（Windows 用 `python` 不是 `python3`——`python3` 會觸發 Microsoft Store 轉址。）

只有在你想讓 AI agent **自動認得**這個技能時才需要下面這步：

```bash
# Claude Code
mkdir -p ~/.claude/skills
ln -s ~/cast-lock-skill ~/.claude/skills/cast-lock

# Codex / 其他 agent:直接叫它讀 ~/cast-lock-skill/SKILL.md 照著做即可,
# 技能本體是 SKILL.md 加兩支腳本,不綁任何特定工具
```

Windows 的 symlink 需要管理員或開發人員模式，比較省事的做法是直接 clone 到技能目錄底下：

```powershell
git clone https://github.com/yazelin/cast-lock-skill "$env:USERPROFILE\.claude\skills\cast-lock"
```

---

## 投一張圖

最輕的貢獻方式。第二話封面就是社群的荒坂小次郎畫的。

### 手繪或自己的工具

想怎麼畫就怎麼畫，不用管上面那套。只有兩件事要注意：

- **角色外觀請對照 [`story/cast.json`](story/cast.json)** 或直接看 `story/refs/` 的設定圖
- **圖上如果要有中文字，交稿前自己確認一次錯字**。第二話封面原稿把「中年攻城屍」寫成「攻城屎」，修起來很麻煩——我們只能像素級補字再重繪一次，你的原始筆觸就不見了

尺寸建議 1024×1536（2:3 直式），webp 或 png 都可以。

### 用 AI 生

```bash
# 1. 寫一段畫面描述,存成 panel.txt
# 2. 組 prompt(會印出參考圖清單與逐項特徵)
python3 ~/cast-lock-skill/build.py --cast story/cast.json --chars kojiro,xiaobai --body panel.txt

# 3. 取參考圖路徑
python3 ~/cast-lock-skill/build.py --cast story/cast.json --chars kojiro,xiaobai --refs-only
```

`build.py` 會在 stderr 提醒你必須把那幾張圖一起傳給生圖工具。**只複製 prompt 是這套方法最常見的失敗方式。**

搭配 [codex-imagegen](https://github.com/yazelin/codex-imagegen-skill)：

```bash
CAST=story/cast.json
CHARS=kojiro,xiaobai
REFS=$(python3 ~/cast-lock-skill/build.py --cast $CAST --chars $CHARS --refs-only)
PROMPT=$(python3 ~/cast-lock-skill/build.py --cast $CAST --chars $CHARS --body panel.txt)
~/.claude/skills/codex-imagegen/codex-imagegen.sh "$PROMPT" out.png $REFS
```

### 交稿前驗收

```bash
python3 ~/cast-lock-skill/check.py --cast story/cast.json --chars kojiro,xiaobai
```

印出逐項清單，**放大看**，一項一項打勾。縮圖看不出金牌上的字有沒有消失。

### 怎麼給我們

開 PR，或直接把檔案丟到 [討論區](https://github.com/yazelin/neko-tensei/discussions)。掛名會寫進 `episodes.json` 的 `credit`，印在那一話最後。

---

## 畫一整話

一話 = 封面 1 張 ＋ 內頁 6 張。

### 1. 先讀創作規範

[`story/README.md`](story/README.md) 是正本，**動手前一定要讀完**。裡面有分工、鐵律、角色特徵表、七種對話框的用法。

重點摘要（細節看正本）：

- **對白跟圖一起生**，不要事後用程式疊字
- **對白一律正體中文**，一頁 3～6 句、句子不要長——改一個字＝整頁重生
- **對話框形狀要跟情緒走**，整頁都是圓角矩形就是錯的
- **前世永遠黑白灰階，貓世界全彩**

### 2. 寫分鏡

開 `story/epN.md`，照 [`story/ep2.md`](story/ep2.md) 的格式：每頁三格，逐格寫「畫什麼／誰說什麼／用哪種框型」，下面附這一頁完整的生圖 prompt。

分鏡跟 prompt 用的是**同一份字**，不要寫兩份。

### 3. 生圖

每頁照上面「用 AI 生」那段跑。參考圖只傳**這一頁真正出場**的角色——2～4 張最乾淨，塞太多角色特徵會互相污染。

有內心 OS 記憶泡的頁面要多帶 `past` 那張前世設定圖。

### 4. 逐頁驗收

```bash
python3 ~/cast-lock-skill/check.py --cast story/cast.json --chars <這頁出場的角色>
```

除了清單上的項目，還要**逐字看對白**：有沒有簡體字、有沒有錯字、有沒有多出來的字。有問題就整頁重生，不要將就。

一個實際發生過的教訓：某一格分鏡寫「上半身透明」，圖出來是一隻完整的貓，那一頁的笑點沒了——而讀分鏡檔完全看不出來。**驗收要看的不是「劇情對不對」，是「這張圖有沒有照描述畫」。**

### 5. 上站

```bash
# 圖放進 images/epN/,然後
# 1. episodes.json 加一段(頁次與 alt 都寫在這裡)
# 2. 產生頁面
python3 build.py
# 3. bump sw.js 的 SHELL 版本號
```

⚠️ **`ep/*.html` 是 `build.py` 的產生檔，改它等於白改。** 要改就改 `build.py` 或 `episodes.json`。

⚠️ **`sw.js` 的 `ASSET` 版本號只有換圖才 bump。** 新增一話有新圖，所以這次 `SHELL` 與 `ASSET` 都要 +1。但如果你只改了文字沒動圖，只 bump `SHELL`——跟著一起 bump 會讓讀者重抓 10 MB 的圖。

### 6. 開 PR

PR 內文請附上那幾張圖（GitHub 可以直接貼），每張下面寫一行「劇本說的」，方便對照。

---

## 加新角色

1. 產一張**設定圖**放 `story/refs/<slug>.webp`——只有這個角色、沒有雜訊、沒有文字
2. `story/cast.json` 加一段：
   - `must`：識別特徵，**寫到字面**（不是「拿武器」，是「腰間掛一枚刻著『守』字的木牌」）
   - `must_not`：**不該出現的東西**，只寫東西本身不要寫成「不要…」（寫 `頭帶或任何帽子`，不要寫 `不要戴頭帶`）
3. `episodes.json` 的 `characters` 加一筆
4. 開一頁 `char/<slug>.html`（照現有的抄，維持左前世／右現在的對照版型）
5. `story/README.md` 的角色特徵表加一列

`must_not` 常被留空，但**漂移大多來自模型自己補東西**。想不出來代表還沒想過它會補什麼。

---

## 授權

圖文採 [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/deed.zh-hant)。投稿即表示同意以此授權釋出，掛名會保留。

## 還有問題

開 [討論區](https://github.com/yazelin/neko-tensei/discussions) 問，或直接開 issue。

技術細節與踩過的坑在 [`AGENTS.md`](AGENTS.md)（那份主要寫給 AI agent，但人看也行）。
