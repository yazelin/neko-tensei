# 自動連載 pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 每週自動產出下一話的劇情、prompt 與圖，開成 PR 讓人一鍵發佈；社群在首頁許願串寫的東西會被讀進企劃。

**Architecture:** 一支驅動腳本 `scripts/next_episode.py` 串起五個階段：讀 canon 與許願 → LLM 出企劃 JSON → 純程式驗企劃 → 逐頁打 codex-image-service → 落檔並跑 `build.py`。企劃與出圖各自可以用旗標跳過或餵檔案，所以整條線在沒有 LLM 金鑰、沒有生圖額度的情況下也跑得完。

**Tech Stack:** Python 3.12 標準函式庫（`urllib`、`json`、`subprocess`、`unittest`）。**不新增任何 pip 相依**——這個 repo 的 `build.py` 就是純 stdlib，維持一致。外部服務走 HTTP：gemini-web（企劃）、codex-image-service（出圖）、`gh` CLI（讀許願、開 PR）。

## Global Constraints

- 設計來源：`docs/superpowers/specs/2026-07-31-auto-episode-pipeline-design.md`
- **只允許一個 pip 相依：`opencc-python-reimplemented`**（簡繁檢查用）。其餘一律 Python 3.12 標準函式庫。`gh` CLI 已安裝可用
- **不自動 merge。** PR 開著等人看
- **這一輪不啟用 cron。** workflow 只留 `workflow_dispatch`，`schedule` 區塊註解掉並附說明。等人工跑過一次、確認 PR 長相之後才由 yazelin 打開
- **這一輪不真的產出第三話上線。** 本機測試只准打 codex-image-service 一次（驗證接線），不准整話跑完
- 一話 = 封面 1 張 ＋ 內頁 6 張。若 `episodes.json` 該話已填社群投稿封面檔名就跳過封面
- 對白一律正體中文，用 `opencc-python-reimplemented` 的 `s2t` 往返比對
- 出圖上限 7 張、重試上限 3 次
- 同時只允許一個開著的 `auto-episode` PR
- 失敗開 issue 標 `auto-episode`，不留半成品 PR
- 對外文字與註解用正體中文
- `ep*.html` 由 `build.py` 產生，永不手改
- **金鑰只從環境變數讀，永遠不進 repo。** 本機測試用的金鑰在 `/home/ct/novel-token-unlimited/漫畫/keys.json`（repo 外），CI 用 GitHub secrets

### 一個曾經想省掉、但證明省不得的相依

寫這份計劃時我為了「不新增 pip 相依」，把 spec 指定的 OpenCC 換成手打的簡體字表。派工前實測，那份 231 字的表裡混進了**正體字**：`那`、`只`、`巨`、`唯`、`反`、`埋`、`准`。其中「那」幾乎每句話都有——驗證器上線後會把絕大多數合法企劃當成含簡體字擋掉。

手打字表的根本問題是沒有正確性保證：我是憑記憶打的，已經證明記憶不可靠，再挑掉幾個字剩下的一樣沒保證。OpenCC 在同一組測試上七個案例全對（含「那」「只」「隻」都正確判為正體）。

所以回到 spec 的原案。這是整份計劃唯一的 pip 相依，套件約 470 KB。

---

## File Structure

| 檔案 | 責任 |
|---|---|
| `scripts/prompt.py`（新增） | 組生圖 prompt。從 scratchpad 搬進 repo，成為 pipeline 與人工重跑共用的單一來源 |
| `scripts/next_episode.py`（新增） | 驅動腳本：canon／許願／企劃／驗證／出圖／落檔，全部是模組層級函式，可被測試 import |
| `scripts/test_next_episode.py`（新增） | stdlib `unittest`。驗純邏輯（驗證器、canon 解析、prompt 組裝、PR 內文），不打外部服務 |
| `.github/workflows/next-episode.yml`（新增） | `workflow_dispatch` 觸發，跑腳本、開 PR。`schedule` 註解掉 |
| `NEXT.md`（修改） | 交接事項：要設哪些 secret、cron 怎麼打開 |

---

## Task 1: 生圖 prompt 模組

把目前只存在於 scratchpad 的 prompt 組裝邏輯搬進 repo。這是第二話實際用過、驗證有效的那一份。

**Files:**
- Create: `scripts/prompt.py`
- Create: `scripts/test_next_episode.py`

**Interfaces:**
- Produces:
  - `REF: dict[str, tuple[str, str]]` — key → (檔案相對路徑, 給模型看的說明)
  - `build_prompt(name: str, keys: list[str], body: str) -> str`
  - `SHAPES: set[str]` — 七種合法框型的名稱
  - `NO_TEXT: set[str]` — 不帶對白與對話框的頁名（`kojiro`、`cover`）

- [x] **Step 1: 寫失敗的測試**

建立 `scripts/test_next_episode.py`：

```python
#!/usr/bin/env python3
"""pipeline 的單元測試。只驗純邏輯,不打任何外部服務。

跑法: python3 -m unittest discover -s scripts -p 'test_*.py' -v
"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent))

import prompt


class TestPrompt(unittest.TestCase):
    def test_參考圖鍵值齊全(self):
        for k in ['style', 'xiaoniao', 'xiaobai', 'uncle', 'leo', 'kojiro', 'past']:
            self.assertIn(k, prompt.REF, k)

    def test_參考圖檔案真的存在(self):
        root = pathlib.Path(__file__).parent.parent
        for k, (rel, _desc) in prompt.REF.items():
            self.assertTrue((root / rel).is_file(), f'{k} 指到不存在的檔案: {rel}')

    def test_內頁帶框型與對白規則(self):
        p = prompt.build_prompt('01', ['style', 'xiaobai'], 'PANEL 1: ...')
        self.assertIn('BALLOON SHAPES', p)
        self.assertIn('TRADITIONAL CHINESE', p)
        self.assertIn('FINAL CHECK', p)

    def test_角色卡不帶框型與對白規則(self):
        p = prompt.build_prompt('kojiro', ['kojiro'], 'A single portrait')
        self.assertNotIn('BALLOON SHAPES', p)
        self.assertNotIn('FINAL CHECK', p)

    def test_封面也不帶框型與對白規則(self):
        p = prompt.build_prompt('cover', ['style', 'xiaoniao'], 'A cover')
        self.assertNotIn('BALLOON SHAPES', p)
        self.assertNotIn('FINAL CHECK', p)

    def test_參考圖清單會逐張標明是誰(self):
        p = prompt.build_prompt('03', ['style', 'kojiro'], 'x')
        self.assertIn('- image 1: ', p)
        self.assertIn('- image 2: ', p)

    def test_出場前世時才帶前世設定(self):
        with_past = prompt.build_prompt('04', ['style', 'past'], 'x')
        without = prompt.build_prompt('04', ['style', 'uncle'], 'x')
        self.assertIn('FORMER HUMAN SELVES', with_past)
        self.assertNotIn('FORMER HUMAN SELVES', without)

    def test_七種框型都在(self):
        self.assertEqual(prompt.SHAPES, {
            'SHOUT', 'OVAL', 'WEAK', 'TREMBLE', 'THOUGHT', 'DEMON', 'CAPTION'})


if __name__ == '__main__':
    unittest.main()
```

- [x] **Step 2: 跑測試確認失敗**

```bash
cd ~/neko-tensei && python3 -m unittest discover -s scripts -p 'test_*.py' 2>&1 | tail -5
```

Expected：`ModuleNotFoundError: No module named 'prompt'`

- [x] **Step 3: 建立 `scripts/prompt.py`**

```python
#!/usr/bin/env python3
"""生圖 prompt 的單一來源。pipeline 與人工重跑共用同一份,別各寫一份。

規則的完整說明在 story/README.md。這裡是那些規則的可執行版本。
"""

# 參考圖。image 1 永遠是第一話成品頁,鎖畫風、上墨感與手寫黑體字;
# 之後接該頁出場角色的設定圖。光靠文字描述角色會漂——寫「圓形金牌」
# 模型會畫成肉球牌,所以設定圖一定要傳。
REF = {
    'style':    ('images/ep1/07.webp',
                 'the finished page 1 art style, inking and hand-lettered bold Chinese type'),
    'xiaoniao': ('story/refs/xiaoniao.webp', 'MAGE CAT model sheet'),
    'xiaobai':  ('story/refs/xiaobai.webp',  'SWORDSMAN CAT model sheet'),
    'uncle':    ('story/refs/uncle.webp',    'SAMURAI CAT model sheet'),
    'leo':      ('story/refs/leo.webp',      'ROGUE CAT model sheet'),
    'kojiro':   ('story/refs/kojiro.webp',   'DEMON KING CAT model sheet'),
    'past':     ('story/refs/past-four.webp',
                 'model sheet of the four heroes FORMER HUMAN SELVES, '
                 'left to right: mage / swordsman / samurai / rogue'),
}

SHAPES = {'SHOUT', 'OVAL', 'WEAK', 'TREMBLE', 'THOUGHT', 'DEMON', 'CAPTION'}

BASE = """Same art style as reference image 1: richly detailed vibrant anime fantasy illustration, painterly digital art, glowing magic particles, floating islands and crystal spires in the sky, saturated blues purples and golds. Vertical manga page, THREE horizontal panels stacked top to bottom, separated by thin white gutters, portrait aspect ratio 2:3."""

SHEET = """CHARACTER SHEET - the model sheets provided as reference images are the authority. Copy every listed feature; a character is wrong if any of these is missing.
- MAGE CAT: long-haired brown-grey Maine Coon. Round thin gold-rimmed glasses, ALWAYS clearly visible on her face. Deep blue robe with gold trim. Tall golden staff topped with a large blue orb. Amber eyes. TWO SMALL BIRDS ARE ALWAYS WITH HER: one plump songbird perched on the head of her staff, and one tiny chick perched on the upper-left of her head like a hair clip. Their species, colour and accessories may differ from panel to panel - birds simply come to her; that is why she is called 小鳥不啾. Neither bird ever opens its beak.
- SWORDSMAN CAT: young brown tabby. Silver plate armour with leather straps and buckles, a red scarf-cape, bare head with NO headband and NO hat of any kind. Big amber eyes, fangs showing, energetic. (His 必勝 headband belongs to his former human self only - never draw it on the cat.)
- SAMURAI CAT: white tiger-striped cat. Dark navy lacquered samurai armour, red cord sash, and a round gold medallion hanging on his chest with the single Chinese character 貓 engraved on it. Blue eyes, stern middle-aged look.
- ROGUE CAT: orange tabby. Black hooded cloak covered in gold paw-print buckles. Brown eyes, sly smirk.
- DEMON KING CAT: enormous dark chocolate-brown long-haired cat. Glowing red eyes, black-and-crimson cape, heavy gold chain across the chest, and a round red crest of a tree above a paw."""

PAST = """

FORMER HUMAN SELVES - only used inside memory bubbles. Copy them from the model sheet exactly; they are NOT generic office workers.
- MAGE's past self: young woman, long straight black hair in a low ponytail, round glasses, a small WHITE BIRD HAIR CLIP above her left ear, cardigan over a tee, an office lanyard round her neck.
- SWORDSMAN's past self: young man, spiky black hair, a WHITE HEADBAND with the two red Chinese characters 必勝 on it, hoodie, mouth open mid-shout, sweating.
- SAMURAI's past self: solidly built middle-aged man, short black hair, stubble, plain black tee, a thick GOLD CHAIN, arms folded. He is muscular and heavy-set, NOT fat and NOT bald.
- ROGUE's past self: young man with LIGHT BLOND hair, black shirt, holding a steaming coffee mug, cool and bored.
THE PAST IS ALWAYS BLACK AND WHITE: render every memory bubble in greyscale with a faint neon-blue glow, exactly like the model sheet. The cat world stays in full colour. This contrast is the whole point."""

SHAPES_BLOCK = """BALLOON SHAPES - each line below names its own balloon shape. Draw that exact shape; do NOT default every balloon to a rounded rectangle. Hand-inked manga feel, slightly irregular outlines, never a perfect geometric shape.
- SHOUT BALLOON: spiky explosion burst with sharp jagged points all around, thick black outline, large bold text.
- OVAL BALLOON: soft hand-drawn organic oval, thin black outline, with a short curved tail pointing at the speaker.
- WEAK BALLOON: small squashed oval with a thin wobbly or dashed outline, small text, deflated feeling.
- TREMBLE BALLOON: oval whose outline shivers in a wavy zigzag, for shock or fear.
- THOUGHT BALLOON: fluffy cloud shape with scalloped edges, tail made of three shrinking circles.
- DEMON BALLOON: black-filled balloon with white text and a ragged spiked edge, heavy and oppressive.
- CAPTION BOX: plain straight-cornered rectangle, the only right-angled box on the page."""

RULES = """DIALOGUE RULES - the most important part, follow exactly:
- All text is TRADITIONAL CHINESE (zh-TW, Taiwan). Copy each string CHARACTER BY CHARACTER exactly as given. Never simplify a character, never substitute a similar-looking character, never invent extra characters, never leave a character out.
- The ONLY text allowed in the whole image is: the dialogue listed below, plus the single character 貓 engraved on the samurai cat's gold medallion. No sound effects, no signature, no watermark, no page numbers, no English captions.
- Keep balloons clear of the characters' faces."""

REMINDER = ("FINAL CHECK before you draw: the balloons on this page must NOT all be the same shape. "
            "Each balloon above is labelled SHOUT / OVAL / WEAK / TREMBLE / THOUGHT / DEMON / CAPTION - "
            "draw exactly that shape for each one. A page where every balloon is a rounded rectangle is wrong.")


# 這些頁面沒有對白,也不該有任何文字:角色卡與封面。
# 封面刻意不烤標題進去——文字烤進圖裡,改一個字就是整張重生。
NO_TEXT = {'kojiro', 'cover'}


def build_prompt(name, keys, body):
    """組一頁的完整 prompt。name 在 NO_TEXT 裡的頁面沒有對白也沒有對話框。"""
    manifest = "REFERENCE IMAGES:\n" + "\n".join(
        f"- image {i + 1}: {REF[k][1]}" for i, k in enumerate(keys))
    sheet = SHEET + PAST if 'past' in keys else SHEET
    parts = [BASE, manifest, sheet]
    if name not in NO_TEXT:
        parts += [SHAPES_BLOCK, RULES]
    out = "\n\n".join(parts) + "\n\n" + body
    if name not in NO_TEXT:
        out += "\n\n" + REMINDER
    return out
```

- [x] **Step 4: 跑測試確認通過**

```bash
cd ~/neko-tensei && python3 -m unittest discover -s scripts -p 'test_*.py' 2>&1 | tail -3
```

Expected：`OK`，8 個測試通過。

- [x] **Step 5: Commit**

```bash
git add scripts/prompt.py scripts/test_next_episode.py
git commit -m "feat(pipeline): 生圖 prompt 進 repo,成為人工與自動共用的單一來源"
```

---

## Task 2: 讀 canon

pipeline 要知道「已經出到第幾話、前面發生過什麼、有哪些伏筆沒收」。

**Files:**
- Create: `scripts/next_episode.py`
- Modify: `scripts/test_next_episode.py`

**Interfaces:**
- Consumes: Task 1 的 `prompt` 模組
- Produces:
  - `ROOT: pathlib.Path` — repo 根目錄
  - `load_canon() -> dict`，鍵為 `next_n`（int，下一話話數）、`episodes`（list，episodes.json 的 episodes）、`rules`（str，story/README.md 全文）、`recent`（str，最近兩話的分鏡全文）

- [x] **Step 1: 加失敗的測試**

在 `scripts/test_next_episode.py` 的 `if __name__` 之前加：

```python
import next_episode as ne


class TestCanon(unittest.TestCase):
    def test_下一話話數接在最後一話之後(self):
        c = ne.load_canon()
        self.assertEqual(c['next_n'], c['episodes'][-1]['n'] + 1)

    def test_帶進創作規範全文(self):
        c = ne.load_canon()
        self.assertIn('對話框的形狀跟著劇情走', c['rules'])
        self.assertIn('必勝', c['rules'])

    def test_帶進最近兩話的分鏡(self):
        c = ne.load_canon()
        self.assertIn('魔力不足', c['recent'])
        self.assertIn('得加 Token', c['recent'])

    def test_話數不重複(self):
        c = ne.load_canon()
        ns = [e['n'] for e in c['episodes']]
        self.assertEqual(len(ns), len(set(ns)))
```

- [x] **Step 2: 跑測試確認失敗**

```bash
cd ~/neko-tensei && python3 -m unittest discover -s scripts -p 'test_*.py' 2>&1 | tail -3
```

Expected：`ModuleNotFoundError: No module named 'next_episode'`

- [x] **Step 3: 建立 `scripts/next_episode.py` 的骨架與 `load_canon`**

```python
#!/usr/bin/env python3
"""自動產出下一話:讀 canon 與許願 → LLM 出企劃 → 驗企劃 → 出圖 → 落檔。

設計在 docs/superpowers/specs/2026-07-31-auto-episode-pipeline-design.md。
只用標準函式庫,不要引入 pip 相依——build.py 也是純 stdlib,維持一致。

跑法:
  python3 scripts/next_episode.py --dry-run          只出企劃並驗證,不出圖不落檔
  python3 scripts/next_episode.py --plan-from p.json 跳過 LLM,用現成企劃
  python3 scripts/next_episode.py                    整條跑完
"""
import json
import pathlib

ROOT = pathlib.Path(__file__).parent.parent


def load_canon():
    """讀出 LLM 寫企劃需要知道的一切。"""
    cfg = json.loads((ROOT / 'episodes.json').read_text('utf-8'))
    eps = cfg['episodes']
    rules = (ROOT / 'story' / 'README.md').read_text('utf-8')
    recent = "\n\n".join(
        (ROOT / 'story' / f"ep{e['n']}.md").read_text('utf-8')
        for e in eps[-2:]
        if (ROOT / 'story' / f"ep{e['n']}.md").is_file())
    return {
        'next_n': eps[-1]['n'] + 1,
        'episodes': eps,
        'rules': rules,
        'recent': recent,
    }
```

- [x] **Step 4: 跑測試確認通過**

```bash
cd ~/neko-tensei && python3 -m unittest discover -s scripts -p 'test_*.py' 2>&1 | tail -3
```

Expected：`OK`，11 個測試通過。

- [x] **Step 5: Commit**

```bash
git add scripts/next_episode.py scripts/test_next_episode.py
git commit -m "feat(pipeline): 讀 canon——已出的話、創作規範、最近兩話分鏡"
```

---

## Task 3: 讀首頁許願串

社群在首頁 giscus 那串寫的東西，是企劃的輸入。**那串可能還不存在**（giscus 要等第一則留言才建 discussion），所以沒有時要安靜地回空清單，不能炸掉。

**Files:**
- Modify: `scripts/next_episode.py`
- Modify: `scripts/test_next_episode.py`

**Interfaces:**
- Consumes: Task 2 的 `ROOT`
- Produces:
  - `WISH_CATEGORY: str` — `'Ideas'`
  - `WISH_TERM: str` — `'劇情許願'`
  - `parse_wishes(payload: dict) -> list[str]` — 純函式，從 GraphQL 回應挑出留言文字
  - `fetch_wishes() -> tuple[list[str], str | None]` — 回（許願清單, 失敗原因）。討論串還不存在是正常的，回 `([], None)`；`gh` 真的失敗才回 `([], '原因')`

- [x] **Step 1: 加失敗的測試**

在 `scripts/test_next_episode.py` 加：

```python
class TestWishes(unittest.TestCase):
    def test_挑出留言文字(self):
        payload = {'data': {'repository': {'discussions': {'nodes': [
            {'title': '劇情許願', 'category': {'name': 'Ideas'},
             'comments': {'nodes': [
                 {'body': '想看小白++單挑魔王'},
                 {'body': '希望里歐的隱形術再出包一次'}]}},
        ]}}}}
        self.assertEqual(ne.parse_wishes(payload),
                         ['想看小白++單挑魔王', '希望里歐的隱形術再出包一次'])

    def test_只收許願那一串不收每話討論(self):
        payload = {'data': {'repository': {'discussions': {'nodes': [
            {'title': '/neko-tensei/ep2.html', 'category': {'name': 'General'},
             'comments': {'nodes': [{'body': '這話好笑'}]}},
            {'title': '劇情許願', 'category': {'name': 'Ideas'},
             'comments': {'nodes': [{'body': '想看貓咪泡溫泉'}]}},
        ]}}}}
        self.assertEqual(ne.parse_wishes(payload), ['想看貓咪泡溫泉'])

    def test_還沒有人許願時回空清單(self):
        self.assertEqual(
            ne.parse_wishes({'data': {'repository': {'discussions': {'nodes': []}}}}), [])

    def test_回應格式不對也不炸(self):
        self.assertEqual(ne.parse_wishes({}), [])
        self.assertEqual(ne.parse_wishes({'data': None}), [])

    def test_空白留言被濾掉(self):
        payload = {'data': {'repository': {'discussions': {'nodes': [
            {'title': '劇情許願', 'category': {'name': 'Ideas'},
             'comments': {'nodes': [{'body': '  '}, {'body': '有效的許願'}]}},
        ]}}}}
        self.assertEqual(ne.parse_wishes(payload), ['有效的許願'])
```

- [x] **Step 2: 跑測試確認失敗**

```bash
cd ~/neko-tensei && python3 -m unittest discover -s scripts -p 'test_*.py' 2>&1 | tail -3
```

Expected：`AttributeError: module 'next_episode' has no attribute 'parse_wishes'`

- [x] **Step 3: 實作**

在 `scripts/next_episode.py` 的 `load_canon` 之後加：

```python
import subprocess

WISH_CATEGORY = 'Ideas'      # 內建分類,首頁許願串就掛在這裡
WISH_TERM = '劇情許願'        # giscus 的 data-term,也是那串 discussion 的標題

_WISH_QUERY = """
{ repository(owner:"yazelin", name:"neko-tensei") {
    discussions(first:20, orderBy:{field:UPDATED_AT, direction:DESC}) {
      nodes { title category { name } comments(first:100) { nodes { body } } } } } }
"""


def parse_wishes(payload):
    """從 GraphQL 回應挑出許願串的留言。純函式,方便測。

    許願串可能還不存在——giscus 要等第一則留言才會建 discussion,
    所以任何形狀對不上的情況都安靜回空清單,不要讓整條 pipeline 倒。
    """
    try:
        nodes = payload['data']['repository']['discussions']['nodes']
    except (KeyError, TypeError):
        return []
    out = []
    for d in nodes or []:
        if (d.get('category') or {}).get('name') != WISH_CATEGORY:
            continue
        if d.get('title') != WISH_TERM:
            continue
        for c in ((d.get('comments') or {}).get('nodes') or []):
            body = (c.get('body') or '').strip()
            if body:
                out.append(body)
    return out


def fetch_wishes():
    """讀首頁許願串。讀不到就回空清單——沒人許願不是錯誤。"""
    try:
        r = subprocess.run(['gh', 'api', 'graphql', '-f', f'query={_WISH_QUERY}'],
                           capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            print('讀許願失敗,當作沒有許願繼續:', r.stderr.strip()[:200])
            return []
        return parse_wishes(json.loads(r.stdout))
    except Exception as e:                      # noqa: BLE001 - 許願是加分項,不該擋住出稿
        print('讀許願失敗,當作沒有許願繼續:', e)
        return []
```

- [x] **Step 4: 跑測試確認通過**

```bash
cd ~/neko-tensei && python3 -m unittest discover -s scripts -p 'test_*.py' 2>&1 | tail -3
```

Expected：`OK`，16 個測試通過。

- [x] **Step 5: 實際打一次 GitHub 確認接線**

```bash
cd ~/neko-tensei && python3 -c "
import sys; sys.path.insert(0,'scripts')
import next_episode as ne
w = ne.fetch_wishes()
print('許願則數:', len(w))
"
```

Expected：`許願則數: 0`（現在還沒有人留言，這正是要驗的——不存在時不會炸）。

- [x] **Step 6: Commit**

```bash
git add scripts/next_episode.py scripts/test_next_episode.py
git commit -m "feat(pipeline): 讀首頁許願串,那串還不存在時安靜回空清單"
```

---

## Task 4: 驗企劃（純程式，這是整條線最重要的守門員）

LLM 出的企劃在花掉出圖額度之前，要先被一組不會妥協的規則擋一遍。

**Files:**
- Modify: `scripts/next_episode.py`
- Modify: `scripts/test_next_episode.py`

**Interfaces:**
- Consumes: Task 1 的 `prompt.SHAPES`
- Produces:
  - `has_simplified(text: str) -> str | None` — 回第一個踩到的簡體字，沒有就回 `None`
  - `validate_plan(plan: dict, next_n: int, titles: list[str]) -> list[str]` — 回問題清單，空清單代表通過

- [x] **Step 1: 加失敗的測試**

在 `scripts/test_next_episode.py` 加：

```python
def _good_plan(n=3):
    """一份會通過驗證的最小企劃,測試用它當基準再逐項弄壞。"""
    shapes = ['SHOUT', 'OVAL', 'WEAK', 'TREMBLE', 'THOUGHT', 'DEMON']
    return {
        'title': '黑塔上的另一個人',
        'desc': '四貓帶著通行證走向黑塔,塔上的魔法陣不是小次郎點的。',
        'beats': ['出發', '塔前受阻', '看見塔頂的人影'],
        'pages': [
            {'n': f'{i:02d}',
             'chars': ['xiaoniao', 'xiaobai'],
             'panels': [
                 {'pos': 'top', 'scene': '四貓走在荒原上',
                  'lines': [{'speaker': 'xiaobai', 'shape': shapes[i - 1],
                             'text': '那座塔越來越近了。'}]},
                 {'pos': 'mid', 'scene': '塔門緊閉',
                  'lines': [{'speaker': 'xiaoniao', 'shape': 'OVAL',
                             'text': '門上有符文。'}]},
             ]}
            for i in range(1, 7)
        ],
    }


class TestSimplified(unittest.TestCase):
    def test_抓到簡體字(self):
        self.assertEqual(ne.has_simplified('这个世界的魔力'), '这')
        self.assertEqual(ne.has_simplified('魔力回来了'), '来')

    def test_正體中文放行(self):
        self.assertIsNone(ne.has_simplified('這個世界的魔力，是我在配的。'))
        self.assertIsNone(ne.has_simplified('得加 Token！'))

    def test_容易被誤判的正體字要放行(self):
        # 這幾個字在手打字表的版本裡被誤收成簡體,「那」幾乎每句話都有,
        # 誤判會讓驗證器擋掉絕大多數合法企劃。
        for s in ['那座塔上的光……不是紅色的。', '隱形只隱一半。這比沒隱還慘。',
                  '四隻空瓶子，還敢慶祝。', '巨大的暗棕色長毛貓',
                  '唯一的線索', '反而露出笑', '埋下伏筆', '準備好了']:
            self.assertIsNone(ne.has_simplified(s), s)

    def test_既有兩話的對白全部放行(self):
        # 最有價值的一條:拿真實內容當回歸測試。手打字表就是敗在這裡——
        # 誤收正體字之後,連自己已經上線的對白都會被判成簡體。
        import pathlib as _p
        root = _p.Path(__file__).parent.parent
        for f in sorted((root / 'story').glob('ep*.md')):
            bad = ne.has_simplified(f.read_text('utf-8'))
            self.assertIsNone(bad, f'{f.name} 出現「{bad}」')

    def test_空字串與None不炸(self):
        self.assertIsNone(ne.has_simplified(''))
        self.assertIsNone(ne.has_simplified(None))


class TestValidate(unittest.TestCase):
    def test_好的企劃通過(self):
        self.assertEqual(ne.validate_plan(_good_plan(), 3, ['我們怎麼變成貓了？！']), [])

    def test_內頁必須六頁(self):
        p = _good_plan(); p['pages'] = p['pages'][:5]
        self.assertTrue(any('六頁' in x or '6' in x for x in ne.validate_plan(p, 3, [])))

    def test_缺欄位會被擋(self):
        for field in ['title', 'desc', 'beats', 'pages']:
            p = _good_plan(); del p[field]
            self.assertTrue(ne.validate_plan(p, 3, []), f'缺 {field} 竟然通過')

    def test_對白含簡體字會被擋(self):
        p = _good_plan()
        p['pages'][0]['panels'][0]['lines'][0]['text'] = '这个世界的魔力'
        errs = ne.validate_plan(p, 3, [])
        self.assertTrue(any('簡體' in e for e in errs), errs)

    def test_框型全部相同會被擋(self):
        p = _good_plan()
        for pg in p['pages']:
            for pn in pg['panels']:
                for ln in pn['lines']:
                    ln['shape'] = 'OVAL'
        errs = ne.validate_plan(p, 3, [])
        self.assertTrue(any('框型' in e for e in errs), errs)

    def test_不存在的框型會被擋(self):
        p = _good_plan()
        p['pages'][0]['panels'][0]['lines'][0]['shape'] = 'ROUNDED'
        self.assertTrue(any('ROUNDED' in e for e in ne.validate_plan(p, 3, [])))

    def test_小次郎不能用內心OS框(self):
        p = _good_plan()
        p['pages'][0]['panels'][0]['lines'][0]['speaker'] = 'kojiro'
        p['pages'][0]['panels'][0]['lines'][0]['shape'] = 'THOUGHT'
        errs = ne.validate_plan(p, 3, [])
        self.assertTrue(any('kojiro' in e and 'THOUGHT' in e for e in errs), errs)

    def test_小次郎用別的框型可以(self):
        p = _good_plan()
        p['pages'][0]['panels'][0]['lines'][0]['speaker'] = 'kojiro'
        p['pages'][0]['panels'][0]['lines'][0]['shape'] = 'DEMON'
        self.assertEqual(ne.validate_plan(p, 3, []), [])

    def test_標題與既有話數重複會被擋(self):
        p = _good_plan()
        p['title'] = '我們怎麼變成貓了？！'
        errs = ne.validate_plan(p, 3, ['我們怎麼變成貓了？！'])
        self.assertTrue(any('標題' in e for e in errs), errs)

    def test_不認識的角色會被擋(self):
        p = _good_plan()
        p['pages'][0]['chars'] = ['xiaoniao', '路人甲']
        self.assertTrue(any('路人甲' in e for e in ne.validate_plan(p, 3, [])))

    def test_沒有對白的頁面會被擋(self):
        p = _good_plan()
        p['pages'][2]['panels'] = [{'pos': 'top', 'scene': '空景', 'lines': []}]
        errs = ne.validate_plan(p, 3, [])
        self.assertTrue(any('對白' in e for e in errs), errs)
```

- [x] **Step 2: 跑測試確認失敗**

```bash
cd ~/neko-tensei && python3 -m unittest discover -s scripts -p 'test_*.py' 2>&1 | tail -3
```

Expected：`AttributeError: module 'next_episode' has no attribute 'has_simplified'`

- [x] **Step 3: 實作**

在 `scripts/next_episode.py` 頂端加 `import prompt`（放在 `import pathlib` 之後、`ROOT` 之前，並先 `import sys; sys.path.insert(0, str(pathlib.Path(__file__).parent))`），然後在 `fetch_wishes` 之後加：

```python
CHARS = {'xiaoniao', 'xiaobai', 'uncle', 'leo', 'kojiro'}

_CC = None


def _cc():
    """OpenCC 轉換器。初始化要讀字典檔,只做一次。"""
    global _CC
    if _CC is None:
        from opencc import OpenCC
        _CC = OpenCC('s2t')
    return _CC


def has_simplified(text):
    """回第一個簡體字;都是正體就回 None。

    用 OpenCC 的 s2t 轉一次再比對,**不要手維護字表**。這份計劃原本為了省掉
    相依而手打了一份 231 字的表,派工前實測發現裡面混進正體字——那、只、
    巨、唯、反、埋、准。「那」幾乎每句話都有,那份表會把絕大多數合法企劃
    當成含簡體字擋掉,而且錯得很安靜。
    """
    if not text:
        return None
    conv = _cc().convert(text)
    if conv == text:
        return None
    for a, b in zip(text, conv):
        if a != b:
            return a
    # s2t 偶爾會讓長度改變(一對多),前面比不出來就退回第一個超出的字
    return (text[len(conv):] or text)[:1] or None


def _lines(plan):
    """把企劃裡所有對白攤平成 (頁, 說話者, 框型, 文字)。"""
    for pg in plan.get('pages') or []:
        for pn in pg.get('panels') or []:
            for ln in pn.get('lines') or []:
                yield pg.get('n'), ln.get('speaker'), ln.get('shape'), ln.get('text')


def validate_plan(plan, next_n, titles):
    """驗企劃。回問題清單,空清單代表通過。

    這是花掉出圖額度之前唯一的守門員,寧可嚴一點——擋錯了頂多重跑一次企劃,
    放過了就是七張圖的額度加上一份沒人想看的草稿 PR。
    """
    errs = []
    if not isinstance(plan, dict):
        return ['企劃不是一個物件']

    for field in ('title', 'desc', 'beats', 'pages'):
        if not plan.get(field):
            errs.append(f'缺欄位:{field}')
    if errs:
        return errs

    if plan['title'] in (titles or []):
        errs.append(f'標題與既有話數重複:{plan["title"]}')

    pages = plan['pages']
    if len(pages) != 6:
        errs.append(f'內頁必須六頁,拿到 {len(pages)} 頁')

    for pg in pages:
        n = pg.get('n')
        if not pg.get('panels'):
            errs.append(f'第 {n} 頁沒有分格')
            continue
        for c in pg.get('chars') or []:
            if c not in CHARS:
                errs.append(f'第 {n} 頁出現不認識的角色:{c}')

        page_shapes = []
        page_lines = 0
        for _n, speaker, shape, text in _lines({'pages': [pg]}):
            page_lines += 1
            if shape not in prompt.SHAPES:
                errs.append(f'第 {n} 頁有不存在的框型:{shape}')
            else:
                page_shapes.append(shape)
            if speaker not in CHARS and speaker is not None:
                errs.append(f'第 {n} 頁有不認識的說話者:{speaker}')
            bad = has_simplified(text)
            if bad:
                errs.append(f'第 {n} 頁對白有簡體字「{bad}」:{text}')
            # 小次郎沒有前世側,內心 OS 的手法對他不成立
            if speaker == 'kojiro' and shape == 'THOUGHT':
                errs.append(f'第 {n} 頁讓 kojiro 用了 THOUGHT 框,他沒有前世可以浮出來')

        if page_lines == 0:
            errs.append(f'第 {n} 頁一句對白都沒有')
        elif len(set(page_shapes)) < 2 and page_lines > 1:
            errs.append(f'第 {n} 頁的框型全部一樣({page_shapes[0]}),框型要跟著情緒走')

    return errs
```

- [x] **Step 4: 跑測試確認通過**

```bash
cd ~/neko-tensei && python3 -m unittest discover -s scripts -p 'test_*.py' 2>&1 | tail -3
```

Expected：`OK`（測試數比前一個任務多 13 條）。若 `test_既有兩話的對白全部放行` 失敗，代表簡繁判斷誤殺了合法正體字——那是 Critical，先查清楚再往下，不要放寬測試。

- [x] **Step 5: Commit**

```bash
git add scripts/next_episode.py scripts/test_next_episode.py
git commit -m "feat(pipeline): 企劃驗證器——六頁、框型分化、簡體字、小次郎不能用 THOUGHT

這是花掉出圖額度之前唯一的守門員,寧可嚴一點。簡繁檢查用內建字表不用
opencc,因為這個 repo 刻意維持純 stdlib;測試會逐字驗證表內每個字都抓得到。"
```

---

## Task 5: 出企劃（LLM）

**Files:**
- Modify: `scripts/next_episode.py`
- Modify: `scripts/test_next_episode.py`

**Interfaces:**
- Consumes: Task 2 的 `load_canon`、Task 3 的 `fetch_wishes`
- Produces:
  - `build_planner_prompt(canon: dict, wishes: list[str]) -> str`
  - `call_llm(text: str) -> str` — 打 gemini-web
  - `make_plan(canon: dict, wishes: list[str]) -> dict`

**背景（brief 之外，實作者要知道的）**：gemini-web 的金鑰在 `/home/ct/novel-token-unlimited/漫畫/keys.json`（`gemini-web` 那個鍵），已驗過可用。**那個檔案在 repo 外面，絕對不要把金鑰寫進任何會 commit 的檔案。** 本機測試用環境變數餵進去。

- [x] **Step 1: 加失敗的測試**

```python
class TestPlannerPrompt(unittest.TestCase):
    def test_prompt_帶進規範與最近分鏡(self):
        canon = ne.load_canon()
        p = ne.build_planner_prompt(canon, [])
        self.assertIn('對話框的形狀跟著劇情走', p)
        self.assertIn('得加 Token', p)

    def test_prompt_要求純JSON(self):
        p = ne.build_planner_prompt(ne.load_canon(), [])
        self.assertIn('JSON', p)

    def test_有許願時會寫進去(self):
        p = ne.build_planner_prompt(ne.load_canon(), ['想看貓咪泡溫泉'])
        self.assertIn('想看貓咪泡溫泉', p)

    def test_沒有許願時明講由AI自己決定(self):
        p = ne.build_planner_prompt(ne.load_canon(), [])
        self.assertIn('由你自己決定要畫什麼', p)

    def test_prompt_列出四種話型(self):
        p = ne.build_planner_prompt(ne.load_canon(), [])
        for k in ['推進主線', '日常番', '烏龍', '角色刻畫']:
            self.assertIn(k, p)

    def test_prompt_明講不必每話推進主線(self):
        p = ne.build_planner_prompt(ne.load_canon(), [])
        self.assertIn('不必每一話都推進主線', p)

    def test_prompt_帶進七種框型(self):
        p = ne.build_planner_prompt(ne.load_canon(), [])
        for s in ['SHOUT', 'DEMON', 'CAPTION']:
            self.assertIn(s, p)
```

- [x] **Step 2: 跑測試確認失敗**

```bash
cd ~/neko-tensei && python3 -m unittest discover -s scripts -p 'test_*.py' 2>&1 | tail -3
```

Expected：`AttributeError: module 'next_episode' has no attribute 'build_planner_prompt'`

- [x] **Step 3: 實作**

在 `scripts/next_episode.py` 加（頂端補 `import os`、`import re`、`import urllib.request`）：

```python
GEMINI_BASE = os.environ.get('GEMINI_WEB_BASE_URL', 'https://ching-tech.ddns.net/gemini-web')
GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')

_PLAN_SHAPE = """{
  "title": "不含「第N話」三個字的標題",
  "kind": "推進主線 | 日常番 | 烏龍 | 角色刻畫",
  "desc": "一到兩句,給網站 meta description 用",
  "beats": ["轉折一", "轉折二", "轉折三"],
  "pages": [
    { "n": "01",
      "chars": ["出場角色的 slug"],
      "panels": [
        { "pos": "top|mid|bottom",
          "scene": "這一格畫什麼,英文,給繪圖模型看",
          "lines": [ { "speaker": "角色 slug", "shape": "框型", "text": "對白" } ] }
      ] }
  ]
}"""


EPISODE_KINDS = """這一話可以是下面任何一種，你自己選最適合的，不必每一話都推進主線：

- **推進主線**：收伏筆、往黑塔走
- **日常番**：不推進劇情，就是四貓在異世界過日子
- **烏龍**：能力出包、誤會、雞飛狗跳
- **角色刻畫**：挖某一位的性格或過去

一年五十二話沒辦法每話都推伏筆，硬推會把線燒完。但不管哪一種，都不可以跟
既有設定矛盾，角色性格也不能走鐘。"""


def build_planner_prompt(canon, wishes):
    wish_block = ("社群這次的許願（要盡量收進去，收不進去的就留給以後）：\n"
                  + "\n".join(f'- {w}' for w in wishes)) if wishes else \
        '這次沒有社群許願，由你自己決定要畫什麼。'
    return f"""你是《轉生成貓貓的我們》的編劇。請企劃第 {canon['next_n']} 話。

這部作品的創作規範（必須遵守）：
────────
{canon['rules']}
────────

最近兩話的分鏡（第 {canon['next_n']} 話要接得上，特別是沒收的伏筆）：
────────
{canon['recent']}
────────

{wish_block}

{EPISODE_KINDS}

請輸出**純 JSON**，不要 markdown 圍籬、不要任何說明文字。格式：
{_PLAN_SHAPE}

硬性要求：
- 內頁正好 6 頁，每頁 2 到 3 個分格
- `shape` 只能是這七種之一：{' / '.join(sorted(prompt.SHAPES))}
- 角色 slug 只能是：{' / '.join(sorted(CHARS))}
- **同一頁的框型不可以全部一樣**，框型要跟著情緒走
- 對白一律正體中文（台灣用語），一頁 3 到 6 句，句子不要長
- kojiro 不可以用 THOUGHT 框，他沒有前世可以浮出來
- 標題不可以跟既有話數重複"""


def _strip_fence(s):
    """LLM 常常還是會包 markdown 圍籬,拆掉。"""
    m = re.search(r'```(?:json)?\s*(.+?)\s*```', s, re.S)
    return m.group(1) if m else s.strip()


def call_llm(text):
    """打 gemini-web 取得企劃文字。"""
    key = os.environ.get('GEMINI_API_KEY', '')
    if not key:
        raise RuntimeError('沒有 GEMINI_API_KEY,無法呼叫 gemini-web')
    url = f'{GEMINI_BASE}/v1beta/models/{GEMINI_MODEL}:generateContent?key={key}'
    body = json.dumps({
        'contents': [{'parts': [{'text': text}]}],
        'generationConfig': {'response_mime_type': 'application/json'},
    }).encode()
    req = urllib.request.Request(url, body, {'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=300) as f:
        payload = json.load(f)
    return payload['candidates'][0]['content']['parts'][0]['text']


def make_plan(canon, wishes):
    return json.loads(_strip_fence(call_llm(build_planner_prompt(canon, wishes))))
```

- [x] **Step 4: 跑測試確認通過**

```bash
cd ~/neko-tensei && python3 -m unittest discover -s scripts -p 'test_*.py' 2>&1 | tail -3
```

Expected：`OK`，36 個測試通過。

- [x] **Step 5: Commit**

```bash
git add scripts/next_episode.py scripts/test_next_episode.py
git commit -m "feat(pipeline): 企劃 prompt 與 gemini-web 呼叫"
```

---

## Task 6: 出圖

**Files:**
- Modify: `scripts/next_episode.py`
- Modify: `scripts/test_next_episode.py`

**Interfaces:**
- Consumes: Task 1 的 `prompt.build_prompt` 與 `prompt.REF`
- Produces:
  - `page_body(page: dict) -> str` — 把企劃的一頁翻成給繪圖模型看的 PANEL 段落
  - `page_refs(page: dict) -> list[str]` — 該頁要傳哪幾張參考圖的 key
  - `generate_image(name: str, keys: list[str], body: str, out: pathlib.Path) -> None`

- [x] **Step 1: 加失敗的測試**

```python
class TestPageBody(unittest.TestCase):
    def test_翻成PANEL段落並帶上框型(self):
        page = {'n': '01', 'chars': ['xiaobai'], 'panels': [
            {'pos': 'top', 'scene': 'four cats on a hill',
             'lines': [{'speaker': 'xiaobai', 'shape': 'SHOUT', 'text': '出發！'}]}]}
        b = ne.page_body(page)
        self.assertIn('PANEL 1 (top): four cats on a hill', b)
        self.assertIn('SHOUT BALLOON', b)
        self.assertIn('出發！', b)

    def test_參考圖第一張永遠是畫風(self):
        page = {'n': '01', 'chars': ['leo', 'uncle'], 'panels': []}
        self.assertEqual(ne.page_refs(page)[0], 'style')

    def test_出場角色都被帶進參考圖(self):
        page = {'n': '01', 'chars': ['leo', 'uncle'], 'panels': []}
        keys = ne.page_refs(page)
        self.assertIn('leo', keys)
        self.assertIn('uncle', keys)

    def test_參考圖不重複(self):
        page = {'n': '01', 'chars': ['leo', 'leo', 'style'], 'panels': []}
        keys = ne.page_refs(page)
        self.assertEqual(len(keys), len(set(keys)))

    def test_有記憶泡才帶前世設定圖(self):
        with_os = {'n': '04', 'chars': ['uncle'], 'panels': [
            {'pos': 'bottom', 'scene': 'x',
             'lines': [{'speaker': 'uncle', 'shape': 'THOUGHT', 'text': '這不就是 code review。'}]}]}
        without = {'n': '01', 'chars': ['uncle'], 'panels': [
            {'pos': 'top', 'scene': 'x',
             'lines': [{'speaker': 'uncle', 'shape': 'OVAL', 'text': '哼。'}]}]}
        self.assertIn('past', ne.page_refs(with_os))
        self.assertNotIn('past', ne.page_refs(without))

    def test_組出來的prompt包含這一頁的對白(self):
        import prompt as pr
        page = {'n': '01', 'chars': ['xiaobai'], 'panels': [
            {'pos': 'top', 'scene': 'x',
             'lines': [{'speaker': 'xiaobai', 'shape': 'SHOUT', 'text': '出發！'}]}]}
        p = pr.build_prompt('01', ne.page_refs(page), ne.page_body(page))
        self.assertIn('出發！', p)
        self.assertIn('FINAL CHECK', p)
```

- [x] **Step 2: 跑測試確認失敗**

```bash
cd ~/neko-tensei && python3 -m unittest discover -s scripts -p 'test_*.py' 2>&1 | tail -3
```

Expected：`AttributeError: module 'next_episode' has no attribute 'page_body'`

- [x] **Step 3: 實作**

在 `scripts/next_episode.py` 加（頂端補 `import base64`、`import time`）：

```python
IMG_BASE = os.environ.get('CODEX_IMAGE_BASE_URL', 'https://ching-tech.ddns.net/codex-image')
SPEAKER_REF = {'xiaoniao': 'xiaoniao', 'xiaobai': 'xiaobai',
               'uncle': 'uncle', 'leo': 'leo', 'kojiro': 'kojiro'}
POS_LABEL = {'top': 'top', 'mid': 'middle', 'middle': 'middle', 'bottom': 'bottom'}


def page_body(page):
    """把企劃的一頁翻成給繪圖模型看的 PANEL 段落。"""
    out = []
    for i, pn in enumerate(page.get('panels') or [], 1):
        pos = POS_LABEL.get(pn.get('pos'), pn.get('pos') or '')
        out.append(f"PANEL {i} ({pos}): {pn.get('scene', '')}")
        for ln in pn.get('lines') or []:
            kind = 'CAPTION BOX' if ln['shape'] == 'CAPTION' else f"{ln['shape']} BALLOON"
            who = SPEAKER_REF.get(ln.get('speaker'), ln.get('speaker') or '')
            out.append(f"  {kind} from {who}: {ln['text']}")
    return "\n".join(out)


def page_refs(page):
    """該頁要傳哪幾張參考圖。image 1 永遠是畫風,之後接出場角色。

    有 THOUGHT 框代表畫面上會有前世的記憶泡,那就要多帶前世設定圖——
    只給文字描述的話四個人全會畫錯。
    """
    keys = ['style']
    for c in page.get('chars') or []:
        k = SPEAKER_REF.get(c)
        if k and k not in keys:
            keys.append(k)
    has_os = any(ln.get('shape') == 'THOUGHT'
                 for pn in page.get('panels') or []
                 for ln in pn.get('lines') or [])
    if has_os and 'past' not in keys:
        keys.append('past')
    return keys


def generate_image(name, keys, body, out):
    """打 .11 的 codex-image-service,把圖存到 out。"""
    key = os.environ.get('CODEX_IMAGE_KEY', '')
    if not key:
        raise RuntimeError('沒有 CODEX_IMAGE_KEY')
    refs = [base64.b64encode((ROOT / prompt.REF[k][0]).read_bytes()).decode() for k in keys]
    body_json = json.dumps({
        'prompt': prompt.build_prompt(name, keys, body),
        'size': '1024x1536', 'quality': 'high', 'count': 1,
        'reference_images_base64': refs,
    }).encode()
    hdr = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
    req = urllib.request.Request(f'{IMG_BASE}/v1/images/jobs', body_json, hdr, method='POST')
    with urllib.request.urlopen(req, timeout=180) as f:
        job = json.load(f)
    print(f'  job {name} {job["id"]}', flush=True)

    t0 = time.time()
    while True:
        time.sleep(15)
        q = urllib.request.Request(f'{IMG_BASE}/v1/images/jobs/{job["id"]}',
                                   headers={'Authorization': hdr['Authorization']})
        with urllib.request.urlopen(q, timeout=60) as f:
            st = json.load(f)
        if st['status'] in ('succeeded', 'failed', 'error'):
            break
        if time.time() - t0 > 2400:
            raise RuntimeError(f'{name} 出圖逾時')
    if st['status'] != 'succeeded':
        raise RuntimeError(f'{name} 出圖失敗: {str(st.get("error"))[:200]}')

    url = st['images'][0]['url']
    if url.startswith('/'):
        url = IMG_BASE + url
    out.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=300) as r, out.open('wb') as w:
        w.write(r.read())
    print(f'  -> {name} ok {int(time.time() - t0)}s', flush=True)
```

- [x] **Step 4: 跑測試確認通過**

```bash
cd ~/neko-tensei && python3 -m unittest discover -s scripts -p 'test_*.py' 2>&1 | tail -3
```

Expected：`OK`，40 個測試通過。

- [x] **Step 5: Commit**

```bash
git add scripts/next_episode.py scripts/test_next_episode.py
git commit -m "feat(pipeline): 企劃翻成生圖 prompt,並打 codex-image-service

有 THOUGHT 框的頁面會自動多帶前世設定圖——只給文字描述的話四個前世
人形全會畫錯,第二話第 04 頁踩過這個坑。"
```

---

## Task 7: 落檔與 PR 內文

**Files:**
- Modify: `scripts/next_episode.py`
- Modify: `scripts/test_next_episode.py`

**Interfaces:**
- Consumes: Task 4 的 `validate_plan`
- Produces:
  - `render_storyboard(plan: dict, n: int) -> str` — 產 `story/epN.md`
  - `episode_entry(plan: dict, n: int, date: str, has_cover: bool) -> dict` — 產 `episodes.json` 的一段
  - `pr_body(plan: dict, n: int, wishes: list[str], wish_err: str | None = None) -> str`

- [x] **Step 1: 加失敗的測試**

```python
class TestRender(unittest.TestCase):
    def test_分鏡檔含標題轉折與每頁對白(self):
        md = ne.render_storyboard(_good_plan(), 3)
        self.assertIn('第三話：黑塔上的另一個人', md)
        self.assertIn('塔前受阻', md)
        self.assertIn('那座塔越來越近了。', md)

    def test_分鏡檔含該頁的生圖prompt(self):
        md = ne.render_storyboard(_good_plan(), 3)
        self.assertIn('PANEL 1 (top):', md)

    def test_episodes條目頁數正確(self):
        e = ne.episode_entry(_good_plan(), 3, '2026-08-07', has_cover=True)
        self.assertEqual(e['n'], 3)
        self.assertEqual(len(e['pages']), 7)
        self.assertEqual(e['pages'][0]['f'], '00-cover.webp')
        self.assertEqual(e['pages'][-1]['f'], '06.webp')

    def test_沒有封面時只有六頁(self):
        e = ne.episode_entry(_good_plan(), 3, '2026-08-07', has_cover=False)
        self.assertEqual(len(e['pages']), 6)
        self.assertEqual(e['pages'][0]['f'], '01.webp')

    def test_每頁都有alt文字(self):
        e = ne.episode_entry(_good_plan(), 3, '2026-08-07', has_cover=True)
        for p in e['pages']:
            self.assertTrue(p['alt'].strip(), p)

    def test_PR內文每頁都附劇本說的(self):
        b = ne.pr_body(_good_plan(), 3, [])
        self.assertIn('劇本說的', b)
        self.assertIn('那座塔越來越近了。', b)

    def test_PR內文列出許願並說明有沒有收進去(self):
        b = ne.pr_body(_good_plan(), 3, ['想看貓咪泡溫泉'])
        self.assertIn('想看貓咪泡溫泉', b)
        self.assertIn('讀了 1 則社群許願', b)

    def test_PR內文標出話型(self):
        p = _good_plan(); p['kind'] = '日常番'
        self.assertIn('話型：日常番', ne.pr_body(p, 3, []))

    def test_沒有許願時PR內文要講明(self):
        b = ne.pr_body(_good_plan(), 3, [])
        self.assertIn('由 AI 自己決定', b)

    def test_PR內文提醒要看的是圖有沒有照劇本畫(self):
        b = ne.pr_body(_good_plan(), 3, [])
        self.assertIn('圖有沒有照劇本畫', b)
```

- [x] **Step 2: 跑測試確認失敗**

```bash
cd ~/neko-tensei && python3 -m unittest discover -s scripts -p 'test_*.py' 2>&1 | tail -3
```

Expected：`AttributeError: module 'next_episode' has no attribute 'render_storyboard'`

- [x] **Step 3: 實作**

```python
CN = '一二三四五六七八九十'
NAME = {'xiaoniao': '小鳥不啾', 'xiaobai': '小白++', 'uncle': '中年攻城屍',
        'leo': '里歐', 'kojiro': '荒坂小次郎'}


def _zh(n):
    return CN[n - 1] if 1 <= n <= 10 else str(n)


def _page_alt(page):
    """用該頁的畫面與對白湊一句 alt。SEO 與無障礙都靠它。"""
    scene = (page.get('panels') or [{}])[0].get('scene', '')
    says = '、'.join(f'{NAME.get(s, s)}「{t}」'
                    for _n, s, _sh, t in _lines({'pages': [page]}))
    return (scene + '：' + says)[:180] if says else scene[:180]


def render_storyboard(plan, n):
    out = [f"# 第{_zh(n)}話：{plan['title']}\n",
           '先讀 [`story/README.md`](README.md) 的鐵律與框型表再動手。'
           '這一話由 pipeline 產出,對白與框型跟生圖 prompt 是同一份。\n',
           '## 這一話在講什麼\n', plan['desc'] + '\n',
           '三個轉折：\n']
    out += [f'{i}. {b}' for i, b in enumerate(plan['beats'], 1)]
    out.append('')
    for pg in plan['pages']:
        out.append(f"\n---\n\n## {pg['n']}\n")
        out.append('| 格 | 畫面 | 對白 | 框型 |')
        out.append('|---|---|---|---|')
        for pn in pg.get('panels') or []:
            first = True
            for ln in pn.get('lines') or []:
                pos = pn.get('pos', '') if first else ''
                scene = pn.get('scene', '') if first else ''
                out.append(f"| {pos} | {scene} | "
                           f"{NAME.get(ln['speaker'], ln['speaker'])}「{ln['text']}」 | {ln['shape']} |")
                first = False
        out.append(f"\n參考圖：{'、'.join(page_refs(pg))}\n")
        out.append('```')
        out.append(page_body(pg))
        out.append('```')
    return "\n".join(out) + "\n"


def episode_entry(plan, n, date, has_cover):
    pages = []
    if has_cover:
        pages.append({'f': '00-cover.webp',
                      'alt': f"第{_zh(n)}話封面：{plan['title']}"})
    for pg in plan['pages']:
        pages.append({'f': f"{pg['n']}.webp", 'alt': _page_alt(pg)})
    return {'n': n, 'title': plan['title'], 'date': date, 'desc': plan['desc'],
            'credit': '劇情與作畫：Claude × gpt-image-2', 'pages': pages}


def pr_body(plan, n, wishes):
    kind = plan.get('kind') or '推進主線'
    out = [f"# 第{_zh(n)}話：{plan['title']}\n",
           f"**話型：{kind}**　"
           + (f"讀了 {len(wishes)} 則社群許願" if wishes else "這次沒有許願，由 AI 自己決定要畫什麼")
           + '\n', plan['desc'] + '\n', '## 三個轉折\n']
    out += [f'{i}. {b}' for i, b in enumerate(plan['beats'], 1)]
    if wishes:
        out.append('\n## 這次讀到的社群許願\n')
        out += [f'- {w}' for w in wishes]
    out.append('\n## 逐頁對照\n')
    out.append('**你要看的不是劇情，是圖有沒有照劇本畫。** '
               '劇情在文字層通常沒問題，會出事的是「劇本寫的」跟「圖畫出來的」之間那道縫——'
               '第二話里歐的「隱形只隱一半」就是分鏡完全正確、圖卻畫成一隻完整的橘貓，'
               '整頁的笑點沒了，而讀分鏡檔案完全看不出來。\n')
    for pg in plan['pages']:
        out.append(f"\n### 第 {pg['n']} 頁\n")
        out.append(f"![第 {pg['n']} 頁](../blob/HEAD/images/ep{n}/{pg['n']}.webp?raw=true)\n")
        out.append('劇本說的：')
        for pn in pg.get('panels') or []:
            out.append(f"- {pn.get('pos', '')}｜{pn.get('scene', '')}")
            for ln in pn.get('lines') or []:
                out.append(f"  - {NAME.get(ln['speaker'], ln['speaker'])}"
                           f"「{ln['text']}」（{ln['shape']}）")
    out.append('\n---\n\n看過覺得沒問題就 merge，站上會自動更新。')
    out.append('有哪一頁不對，關掉 PR 就好，下週會重新產一份。\n')
    out.append('🤖 Generated with [Claude Code](https://claude.com/claude-code)')
    return "\n".join(out)
```

- [x] **Step 4: 跑測試確認通過**

```bash
cd ~/neko-tensei && python3 -m unittest discover -s scripts -p 'test_*.py' 2>&1 | tail -3
```

Expected：`OK`，52 個測試通過。

- [x] **Step 5: Commit**

```bash
git add scripts/next_episode.py scripts/test_next_episode.py
git commit -m "feat(pipeline): 產分鏡檔、episodes.json 條目與 PR 內文

PR 內文逐頁附「劇本說的」,因為人工閘門要看的不是劇情而是
圖有沒有照劇本畫——第二話里歐那格是活教材。"
```

---

## Task 8: 驅動腳本與旗標

把前面七個任務串起來，並提供在沒有 LLM 金鑰、沒有生圖額度時也跑得完的路徑。

**Files:**
- Modify: `scripts/next_episode.py`
- Modify: `scripts/test_next_episode.py`

**Interfaces:**
- Consumes: 前面全部
- Produces: `main(argv: list[str]) -> int`，以及命令列旗標 `--dry-run`、`--plan-from FILE`、`--plan-only FILE`、`--skip-images`

- [x] **Step 1: 加失敗的測試**

```python
import io
import json as _json
import tempfile
from contextlib import redirect_stdout


class TestMain(unittest.TestCase):
    def test_plan_from_搭配_dry_run_不碰任何檔案(self):
        with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False,
                                         encoding='utf-8') as f:
            _json.dump(_good_plan(), f)
            path = f.name
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = ne.main(['--plan-from', path, '--dry-run'])
        self.assertEqual(rc, 0, buf.getvalue())
        self.assertIn('企劃通過驗證', buf.getvalue())

    def test_壞企劃會讓程式回非零並印出原因(self):
        bad = _good_plan()
        bad['pages'][0]['panels'][0]['lines'][0]['text'] = '这个世界'
        with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False,
                                         encoding='utf-8') as f:
            _json.dump(bad, f)
            path = f.name
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = ne.main(['--plan-from', path, '--dry-run'])
        self.assertEqual(rc, 1)
        self.assertIn('簡體', buf.getvalue())
```

- [x] **Step 2: 跑測試確認失敗**

```bash
cd ~/neko-tensei && python3 -m unittest discover -s scripts -p 'test_*.py' 2>&1 | tail -3
```

Expected：`AttributeError: module 'next_episode' has no attribute 'main'`

- [x] **Step 3: 實作**

```python
import argparse
import datetime


def publish(plan, n, has_cover):
    """落檔:圖已經在 images/epN/ 了,這裡處理分鏡、episodes.json 與 build。"""
    (ROOT / 'story' / f'ep{n}.md').write_text(render_storyboard(plan, n), 'utf-8')

    cfg_path = ROOT / 'episodes.json'
    cfg = json.loads(cfg_path.read_text('utf-8'))
    date = datetime.date.today().isoformat()
    cfg['episodes'].append(episode_entry(plan, n, date, has_cover))
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + '\n', 'utf-8')

    # sw.js:殼要 bump(多了一頁 epN.html);ASSET 只有換圖才 bump,
    # 但這次確實多了新圖,所以兩個都要動。
    sw = ROOT / 'sw.js'
    t = sw.read_text('utf-8')
    for kind in ('shell', 'asset'):
        m = re.search(rf"nt-{kind}-v(\d+)", t)
        t = t.replace(m.group(0), f"nt-{kind}-v{int(m.group(1)) + 1}")
    sw.write_text(t, 'utf-8')

    subprocess.run(['python3', str(ROOT / 'build.py')], check=True, cwd=ROOT)


def main(argv=None):
    ap = argparse.ArgumentParser(description='產出下一話')
    ap.add_argument('--dry-run', action='store_true', help='只出企劃並驗證,不出圖不落檔')
    ap.add_argument('--plan-from', metavar='FILE', help='跳過 LLM,用現成的企劃 JSON')
    ap.add_argument('--plan-only', metavar='FILE', help='只出企劃,存成 FILE 後結束')
    ap.add_argument('--skip-images', action='store_true', help='不出圖,其餘照跑')
    a = ap.parse_args(argv)

    canon = load_canon()
    n = canon['next_n']
    titles = [e['title'] for e in canon['episodes']]
    wishes, wish_err = fetch_wishes()
    if wish_err:
        print('警告:讀許願失敗,這一話會當作沒有許願繼續 —', wish_err)
    print(f'第 {n} 話;讀到 {len(wishes)} 則許願')

    if a.plan_from:
        plan = json.loads(pathlib.Path(a.plan_from).read_text('utf-8'))
    else:
        plan = make_plan(canon, wishes)
        if a.plan_only:
            pathlib.Path(a.plan_only).write_text(
                json.dumps(plan, ensure_ascii=False, indent=2), 'utf-8')
            print('企劃已存到', a.plan_only)
            return 0

    errs = validate_plan(plan, n, titles)
    if errs:
        print('企劃沒過驗證:')
        for e in errs:
            print(' -', e)
        return 1
    print('企劃通過驗證:', plan['title'])

    if a.dry_run:
        return 0

    has_cover = False
    if not a.skip_images:
        for pg in plan['pages']:
            out = ROOT / f'images/ep{n}' / f"{pg['n']}.webp"
            generate_image(pg['n'], page_refs(pg), page_body(pg), out)
        has_cover = (ROOT / f'images/ep{n}/00-cover.webp').is_file()

    publish(plan, n, has_cover)
    (ROOT / f'.pr-body-ep{n}.md').write_text(pr_body(plan, n, wishes, wish_err), 'utf-8')
    print('落檔完成。PR 內文在 .pr-body-ep%d.md' % n)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
```

- [x] **Step 4: 跑測試確認通過**

```bash
cd ~/neko-tensei && python3 -m unittest discover -s scripts -p 'test_*.py' 2>&1 | tail -3
```

Expected：`OK`，54 個測試通過。

- [x] **Step 5: 真的出一次企劃（本機端到端，打 gemini-web）**

金鑰在 `/home/ct/novel-token-unlimited/漫畫/keys.json`。**只用環境變數餵，不要寫進任何檔案。**

```bash
cd ~/neko-tensei && export GEMINI_API_KEY=$(python3 -c "import json;print(json.load(open('/home/ct/novel-token-unlimited/漫畫/keys.json'))['gemini-web'])")
timeout 900 python3 scripts/next_episode.py --plan-only /tmp/ep3-plan.json 2>&1 | tail -5
python3 -c "
import json,sys; sys.path.insert(0,'scripts'); import next_episode as ne
p=json.load(open('/tmp/ep3-plan.json'))
print('標題:', p.get('title')); print('頁數:', len(p.get('pages',[])))
errs=ne.validate_plan(p,3,[e['title'] for e in ne.load_canon()['episodes']])
print('驗證:', errs or '通過')"
```

Expected：印出標題與頁數。**如果驗證沒過是預期的**——那正好證明驗證器在工作。把失敗原因記進報告，然後改用 `--plan-from` 餵一份手寫的合格企劃繼續下一步。不要為了讓它過而放寬驗證規則。

- [x] **Step 6: Commit**

```bash
git add scripts/next_episode.py scripts/test_next_episode.py
git commit -m "feat(pipeline): 驅動腳本與旗標,沒有金鑰也跑得完前半段"
```

---

## Task 9: 封面與重試

spec 的護欄要求「企劃不過重試一次、出圖重試三次」，也要求 pipeline 產封面（除非 `episodes.json` 已經填了社群投稿的封面）。前面八個任務都沒做這兩件事。

**Files:**
- Modify: `scripts/next_episode.py`
- Modify: `scripts/test_next_episode.py`

**Interfaces:**
- Consumes: Task 5 的 `make_plan`、Task 6 的 `generate_image`、Task 8 的 `main`
- Produces:
  - `cover_body(plan: dict) -> str`
  - `plan_with_retry(canon: dict, wishes: list[str], titles: list[str], n: int) -> dict` — 失敗丟 `RuntimeError`
  - `IMG_RETRIES: int` — `3`

- [x] **Step 1: 加失敗的測試**

在 `scripts/test_next_episode.py` 加：

```python
class TestCover(unittest.TestCase):
    def test_封面描述帶進三個轉折(self):
        b = ne.cover_body(_good_plan())
        for beat in _good_plan()['beats']:
            self.assertIn(beat, b)

    def test_封面明確要求全員入鏡且無文字(self):
        b = ne.cover_body(_good_plan())
        self.assertIn('NO text', b)
        self.assertIn('all five', b.lower() + b)

    def test_封面用的prompt不含對白規則(self):
        import prompt as pr
        p = pr.build_prompt('cover', ['style'], ne.cover_body(_good_plan()))
        self.assertNotIn('BALLOON SHAPES', p)


class TestRetry(unittest.TestCase):
    def test_第一次就過就不重試(self):
        calls = []

        def fake(canon, wishes):
            calls.append(1)
            return _good_plan()

        orig, ne.make_plan = ne.make_plan, fake
        try:
            ne.plan_with_retry(ne.load_canon(), [], [], 3)
        finally:
            ne.make_plan = orig
        self.assertEqual(len(calls), 1)

    def test_第一次不過會重試第二次(self):
        calls = []

        def fake(canon, wishes):
            calls.append(1)
            if len(calls) == 1:
                bad = _good_plan()
                bad['pages'] = bad['pages'][:3]
                return bad
            return _good_plan()

        orig, ne.make_plan = ne.make_plan, fake
        try:
            plan = ne.plan_with_retry(ne.load_canon(), [], [], 3)
        finally:
            ne.make_plan = orig
        self.assertEqual(len(calls), 2)
        self.assertEqual(plan['title'], _good_plan()['title'])

    def test_連兩次都不過就丟例外並帶上原因(self):
        def fake(canon, wishes):
            bad = _good_plan()
            bad['pages'] = bad['pages'][:2]
            return bad

        orig, ne.make_plan = ne.make_plan, fake
        try:
            with self.assertRaises(RuntimeError) as cm:
                ne.plan_with_retry(ne.load_canon(), [], [], 3)
        finally:
            ne.make_plan = orig
        self.assertIn('六頁', str(cm.exception))

    def test_出圖重試上限是三次(self):
        self.assertEqual(ne.IMG_RETRIES, 3)
```

- [x] **Step 2: 跑測試確認失敗**

```bash
cd ~/neko-tensei && python3 -m unittest discover -s scripts -p 'test_*.py' 2>&1 | tail -3
```

Expected：`AttributeError: module 'next_episode' has no attribute 'cover_body'`

- [x] **Step 3: 實作**

在 `scripts/next_episode.py` 的 `generate_image` 之後加：

```python
IMG_RETRIES = 3


def cover_body(plan):
    """封面的畫面描述。刻意不把標題烤進圖裡——文字進了圖,改一個字就是整張重生。

    標題會出現在網頁上,不需要也不應該畫在封面裡。
    """
    beats = '; '.join(plan.get('beats') or [])
    return (f"A single dramatic cover illustration, NOT a multi-panel page, "
            f"and with NO text, NO letters, NO title, NO watermark anywhere in the image.\n"
            f"All five cats together in one heroic group composition: the MAGE CAT, "
            f"the SWORDSMAN CAT, the SAMURAI CAT, the ROGUE CAT, and looming behind them "
            f"the DEMON KING CAT.\n"
            f"The mood and setting come from this episode: {plan.get('desc', '')}\n"
            f"Key moments of the episode, use them to choose the setting and lighting: {beats}\n"
            f"Portrait aspect ratio 2:3, same painterly vibrant anime fantasy style as "
            f"reference image 1.")


def generate_with_retry(name, keys, body, out):
    """出圖失敗重試。服務端偶爾會回 502(內容重複偵測),再打一次通常就好。"""
    last = None
    for i in range(1, IMG_RETRIES + 1):
        try:
            generate_image(name, keys, body, out)
            return
        except Exception as e:                  # noqa: BLE001
            last = e
            print(f'  {name} 第 {i}/{IMG_RETRIES} 次失敗: {str(e)[:160]}', flush=True)
            if i < IMG_RETRIES:
                time.sleep(20)
    raise RuntimeError(f'{name} 出圖連 {IMG_RETRIES} 次都失敗: {last}')


def plan_with_retry(canon, wishes, titles, n):
    """企劃不過就重試一次,再不過就放棄。

    重試時不改 prompt——同一份 prompt 再擲一次,因為這是機率性輸出,
    第一次不過通常不是 prompt 寫壞了。連兩次都不過才是真的有問題。
    """
    errs = []
    for attempt in (1, 2):
        plan = make_plan(canon, wishes)
        errs = validate_plan(plan, n, titles)
        if not errs:
            return plan
        print(f'企劃第 {attempt}/2 次沒過:')
        for e in errs:
            print(' -', e)
    raise RuntimeError('企劃連兩次都沒過驗證:' + '；'.join(errs))
```

- [x] **Step 4: 讓 `main` 用上重試與封面**

把 `main` 裡這一段：

```python
    if a.plan_from:
        plan = json.loads(pathlib.Path(a.plan_from).read_text('utf-8'))
    else:
        plan = make_plan(canon, wishes)
        if a.plan_only:
            pathlib.Path(a.plan_only).write_text(
                json.dumps(plan, ensure_ascii=False, indent=2), 'utf-8')
            print('企劃已存到', a.plan_only)
            return 0

    errs = validate_plan(plan, n, titles)
    if errs:
        print('企劃沒過驗證:')
        for e in errs:
            print(' -', e)
        return 1
    print('企劃通過驗證:', plan['title'])
```

換成：

```python
    if a.plan_from:
        plan = json.loads(pathlib.Path(a.plan_from).read_text('utf-8'))
        errs = validate_plan(plan, n, titles)
        if errs:
            print('企劃沒過驗證:')
            for e in errs:
                print(' -', e)
            return 1
    else:
        try:
            plan = plan_with_retry(canon, wishes, titles, n)
        except RuntimeError as e:
            print(e)
            return 1
        if a.plan_only:
            pathlib.Path(a.plan_only).write_text(
                json.dumps(plan, ensure_ascii=False, indent=2), 'utf-8')
            print('企劃已存到', a.plan_only)
            return 0
    print('企劃通過驗證:', plan['title'])
```

再把出圖那一段：

```python
    has_cover = False
    if not a.skip_images:
        for pg in plan['pages']:
            out = ROOT / f'images/ep{n}' / f"{pg['n']}.webp"
            generate_image(pg['n'], page_refs(pg), page_body(pg), out)
        has_cover = (ROOT / f'images/ep{n}/00-cover.webp').is_file()
```

換成：

```python
    cover_path = ROOT / f'images/ep{n}/00-cover.webp'
    if not a.skip_images:
        # 社群投稿的封面永遠優先:已經有檔案就不要蓋掉
        if not cover_path.is_file():
            generate_with_retry('cover', ['style', 'xiaoniao', 'xiaobai', 'uncle',
                                          'leo', 'kojiro'],
                                cover_body(plan), cover_path)
        else:
            print('封面已存在,跳過(社群投稿優先)')
        for pg in plan['pages']:
            generate_with_retry(pg['n'], page_refs(pg), page_body(pg),
                                ROOT / f'images/ep{n}' / f"{pg['n']}.webp")
    has_cover = cover_path.is_file()
```

- [x] **Step 5: 跑測試確認通過**

```bash
cd ~/neko-tensei && python3 -m unittest discover -s scripts -p 'test_*.py' 2>&1 | tail -3
```

Expected：`OK`，62 個測試通過。

- [x] **Step 6: 確認 `--plan-from --dry-run` 還是好的**

```bash
cd ~/neko-tensei && python3 -c "
import json,sys,tempfile; sys.path.insert(0,'scripts')
import test_next_episode as t
p=tempfile.NamedTemporaryFile('w',suffix='.json',delete=False,encoding='utf-8')
json.dump(t._good_plan(),p); p.close()
import next_episode as ne
print('rc =', ne.main(['--plan-from',p.name,'--dry-run']))"
```

Expected：印出 `企劃通過驗證: 黑塔上的另一個人` 與 `rc = 0`。

- [x] **Step 7: Commit**

```bash
git add scripts/next_episode.py scripts/prompt.py scripts/test_next_episode.py
git commit -m "feat(pipeline): 封面與重試

封面刻意不把標題烤進圖裡——文字進了圖,改一個字就是整張重生。標題在
網頁上就好。社群投稿的封面永遠優先,已經有檔案就不蓋掉。

企劃不過重試一次(同一份 prompt 再擲一次,機率性輸出第一次不過通常不是
prompt 寫壞了);出圖重試三次,服務端偶爾回 502 內容重複偵測。"
```

---

## Task 10: GitHub Actions workflow

**Files:**
- Create: `.github/workflows/next-episode.yml`
- Modify: `NEXT.md`

**Interfaces:**
- Consumes: Task 9 的 `scripts/next_episode.py` 與它產出的 `.pr-body-epN.md`

- [x] **Step 1: 建立 workflow**

```yaml
name: 下一話

# cron 先不開。等人工用 workflow_dispatch 跑過一次、確認 PR 的樣子與
# 手機可讀性之後,再由 yazelin 把下面三行的註解拿掉。
on:
  # schedule:
  #   - cron: '0 14 * * 5'   # 每週五 台北 22:00
  workflow_dispatch:

permissions:
  contents: write
  pull-requests: write
  issues: write
  discussions: read

concurrency:
  group: next-episode
  cancel-in-progress: false

jobs:
  draft:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: 裝相依（整條線唯一的 pip 套件）
        run: pip install --quiet opencc-python-reimplemented

      - name: 確認沒有還開著的草稿 PR
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          open=$(gh pr list --label auto-episode --state open --json number --jq 'length')
          if [ "$open" != "0" ]; then
            echo "::error::已經有 $open 個開著的 auto-episode PR,先處理完再產下一話"
            exit 1
          fi

      - name: 確認 secrets 齊全
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          CODEX_IMAGE_KEY: ${{ secrets.CODEX_IMAGE_KEY }}
        run: |
          miss=0
          [ -z "$GEMINI_API_KEY" ]  && { echo "::error::缺 GEMINI_API_KEY";  miss=1; }
          [ -z "$CODEX_IMAGE_KEY" ] && { echo "::error::缺 CODEX_IMAGE_KEY"; miss=1; }
          exit $miss

      - name: 產出下一話
        id: gen
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          GEMINI_WEB_BASE_URL: ${{ secrets.GEMINI_WEB_BASE_URL }}
          CODEX_IMAGE_KEY: ${{ secrets.CODEX_IMAGE_KEY }}
          CODEX_IMAGE_BASE_URL: ${{ secrets.CODEX_IMAGE_BASE_URL }}
        run: python3 scripts/next_episode.py

      - name: 開 PR
        if: success()
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          N=$(python3 -c "import json;print(json.load(open('episodes.json'))['episodes'][-1]['n'])")
          BR="auto/ep$N"
          git config user.name  "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git checkout -b "$BR"
          git add -A
          git rm --cached ".pr-body-ep$N.md" >/dev/null 2>&1 || true
          git commit -m "feat: 第 $N 話草稿(自動產出,待人工確認)"
          git push -u origin "$BR"
          gh pr create --base main --head "$BR" \
            --title "第 $N 話草稿——待你看過再 merge" \
            --body-file ".pr-body-ep$N.md" \
            --label auto-episode

      - name: 失敗就開 issue
        if: failure()
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          gh issue create --label auto-episode \
            --title "自動產出下一話失敗（$(date -u +%Y-%m-%d)）" \
            --body "跑失敗了，沒有留下半成品 PR。記錄在 ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"
```

- [x] **Step 2: 檢查 YAML 語法**

```bash
cd ~/neko-tensei && python3 -c "
import json,urllib.request,sys
# 沒有 pyyaml 可用,改用 gh 的 workflow 解析:先確認檔案讀得進來、縮排一致
t=open('.github/workflows/next-episode.yml',encoding='utf-8').read()
bad=[i for i,l in enumerate(t.split(chr(10)),1) if l.rstrip()!=l.rstrip(' ') ]
print('行數:', len(t.split(chr(10))))
print('有 tab 縮排的行:', [i for i,l in enumerate(t.split(chr(10)),1) if l.startswith(chr(9))] or '無')
"
```

Expected：`有 tab 縮排的行: 無`。

- [x] **Step 3: 建立 label**

```bash
cd ~/neko-tensei && gh label create auto-episode --color 8A63D2 --description "自動產出的草稿,待人工確認" 2>&1 | tail -1
```

Expected：建立成功，或 `already exists`（都可以）。

- [x] **Step 4: 更新 `NEXT.md` 的交接事項**

把 `NEXT.md` 的「## 自動連載 pipeline（下一個要做的）」整段換成：

```markdown
## 自動連載 pipeline（已實作，未啟用）

程式在 `scripts/next_episode.py`，workflow 在 `.github/workflows/next-episode.yml`。

**要 yazelin 做的三件事：**

1. 設 repo secrets（`gh secret set <NAME>`）——目前 `gh secret list` 是空的：
   - `GEMINI_API_KEY`、`CODEX_IMAGE_KEY`：**這兩把是必要的**。值在 repo 外的
     `/home/ct/novel-token-unlimited/漫畫/keys.json`，鍵名分別是 `gemini-web`
     與 `codex-image-service`。**不是 catime 那組**，別拿錯
   - `GEMINI_WEB_BASE_URL`、`CODEX_IMAGE_BASE_URL`：**可以不設**。腳本內建
     `https://ching-tech.ddns.net/gemini-web` 與 `.../codex-image`，只有服務
     搬家才需要用 secret 覆蓋掉
2. 到 Actions 頁面手動跑一次「下一話」，看 PR 的樣子與手機可讀性
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
```

- [x] **Step 5: Commit**

```bash
git add .github/workflows/next-episode.yml NEXT.md
git commit -m "feat(pipeline): GitHub Actions workflow,cron 先不開

只留 workflow_dispatch。等人工跑過一次、確認 PR 長相與手機可讀性之後,
再由 yazelin 把 schedule 的註解拿掉。失敗開 issue 不留半成品 PR;
開跑前先擋「已經有開著的 auto-episode PR」。"
```

---

## Task 11: 本機端到端試跑並開 PR

這一步會真的產出檔案。**不 merge、不啟用 cron、不整話出圖。**

**Files:**
- 不新增檔案；產出的第三話檔案只留在分支上供人檢視

- [x] **Step 1: 確認整套測試通過**

```bash
cd ~/neko-tensei && python3 -m unittest discover -s scripts -p 'test_*.py' 2>&1 | tail -3
NODE_PATH=$(npm root -g) node scripts/verify-mobile.js 2>&1 | tail -2
```

Expected：`OK` 與 `42/42 通過`（pipeline 不該弄壞行動版）。

- [x] **Step 2: 用 Task 8 產出的企劃跑一次不出圖的完整流程**

```bash
cd ~/neko-tensei && python3 scripts/next_episode.py --plan-from /tmp/ep3-plan.json --skip-images 2>&1 | tail -5
git status --short | head -10
```

Expected：`story/ep3.md`、`episodes.json`、`sw.js`、`ep3.html`、`index.html`、`sitemap.xml` 都有變動。

若企劃在 Task 9 沒通過驗證，先手寫一份合格的存成 `/tmp/ep3-plan.json` 再跑——**不要放寬驗證規則來遷就**。

- [x] **Step 3: 檢查產出的東西長得對不對**

```bash
cd ~/neko-tensei && head -30 story/ep3.md && echo "=== ep3.html 的圖 ===" && grep -c 'images/ep3/' ep3.html && echo "=== sw 版本 ===" && grep -E "^const (SHELL|ASSET)" sw.js
```

Expected：分鏡檔有標題與逐頁表格；`ep3.html` 參照 6 張圖；`SHELL`／`ASSET` 都比原本大 1。

- [x] **Step 4: 只出一張圖，驗證生圖那一段真的接得上**

**只出一張，不要整話跑完。** 這一步是驗接線，不是產內容。

```bash
cd ~/neko-tensei && export CODEX_IMAGE_KEY=$(python3 -c "import json;print(json.load(open('/home/ct/novel-token-unlimited/漫畫/keys.json'))['codex-image-service'])")
python3 -c "
import sys, pathlib, json; sys.path.insert(0,'scripts')
import next_episode as ne
plan = json.load(open('/tmp/ep3-plan.json'))
pg = plan['pages'][0]
out = pathlib.Path('/tmp/ep3-p01-test.png')
ne.generate_image(pg['n'], ne.page_refs(pg), ne.page_body(pg), out)
print('產出:', out, out.stat().st_size, 'bytes')
"
```

Expected：約 3–4 分鐘後印出檔案路徑與大小（3 MB 上下）。這張圖**不要**放進 repo。

- [x] **Step 5: 目視那張圖，確認 prompt 真的組對了**

用 Read 工具打開 `/tmp/ep3-p01-test.png`（先縮到 512 寬），確認：

```bash
cd ~/neko-tensei && python3 -c "
from PIL import Image
Image.open('/tmp/ep3-p01-test.png').resize((512,768), Image.LANCZOS).save('/tmp/ep3-p01-preview.png')
print('預覽: /tmp/ep3-p01-preview.png')"
```

要看的四件事：三格橫幅、對白是正體中文、框型有分化（不是整頁圓角矩形）、角色特徵對得上（`貓` 字金牌、小白++ 沒有頭帶、小鳥不啾有眼鏡與兩隻鳥）。

**有任何一項不對，記進報告，不要自己改 prompt 去遷就**——那是下一輪要處理的事，這一步的目的是知道現況。

- [x] **Step 6: 把第三話的產出從分支上撤掉**

這一輪的目的是驗證 pipeline，不是發佈第三話。內容要等 yazelin 看過再決定。

```bash
cd ~/neko-tensei && git checkout -- episodes.json sw.js && rm -rf images/ep3 story/ep3.md ep3.html .pr-body-ep3.md && python3 build.py && git status --short
```

Expected：`git status --short` 只剩 pipeline 本身的檔案，沒有 `ep3` 相關的東西。

- [x] **Step 7: 確認整套測試仍然通過**

```bash
cd ~/neko-tensei && python3 -m unittest discover -s scripts -p 'test_*.py' 2>&1 | tail -3
NODE_PATH=$(npm root -g) node scripts/verify-mobile.js 2>&1 | tail -2
```

Expected：`OK` 與 `42/42 通過`。

- [x] **Step 8: 開 PR，不要 merge**

```bash
cd ~/neko-tensei && git push -u origin feat/auto-episode
gh pr create --base main --head feat/auto-episode \
  --title "feat: 自動連載 pipeline（已實作，cron 未啟用）" \
  --body-file docs/superpowers/plans/.pr-body-pipeline.md
```

PR 內文要自己寫進 `docs/superpowers/plans/.pr-body-pipeline.md`（寫完就刪，別 commit），內容至少涵蓋：

- 這條線做什麼、五個階段各是什麼
- **驗證器擋了什麼**——附上本機實跑的輸出
- 本機端到端的結果：企劃真的出來了嗎？通過驗證了嗎？那張測試圖對不對？
- **哪些事還沒做、要 yazelin 動手**：設四個 secret、手動跑一次、確認之後才打開 cron
- 誠實列出沒驗過的環節（例如 workflow 本身在 GitHub 上從沒跑過）

**不要 merge。**

---

## 交付狀態

這份計劃跑完之後，狀態應該是：

- `feat/auto-episode` 分支上有完整的 pipeline，PR 開著
- 單元測試涵蓋所有純邏輯（驗證器、canon、許願解析、prompt 組裝、PR 內文）
- 企劃那一段本機真的打過 gemini-web，出過一份企劃並過了驗證器
- 生圖那一段本機真的打過 codex-image-service，出過一張圖並目視過
- **cron 沒開、PR 沒 merge、第三話沒上線**
- `NEXT.md` 寫清楚剩下三件要 yazelin 動手的事
