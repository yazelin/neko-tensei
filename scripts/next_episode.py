#!/usr/bin/env python3
"""自動產出下一話:讀 canon 與許願 → LLM 出企劃 → 驗企劃 → 出圖 → 落檔。

設計在 docs/superpowers/specs/2026-07-31-auto-episode-pipeline-design.md。
只有兩個 pip 相依:`opencc-python-reimplemented`(驗簡繁)與 `pillow`
(落檔重壓 webp——服務端回的是近無損檔,一頁 3.7 MB,不壓一話就 23 MB,
而這個站是 PWA,圖全部會被 precache)。其餘一律標準函式庫,build.py 仍是
純 stdlib。

跑法:
  python3 scripts/next_episode.py --dry-run          只出企劃並驗證,不出圖不落檔
  python3 scripts/next_episode.py --plan-from p.json 跳過 LLM,用現成企劃
  python3 scripts/next_episode.py                    整條跑完
"""
import argparse
import base64
import datetime
import json
import os
import pathlib
import re
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import prompt

ROOT = pathlib.Path(__file__).parent.parent

WISH_CATEGORY = 'Ideas'      # 內建分類,首頁許願串就掛在這裡
WISH_TERM = '劇情許願'        # giscus 的 data-term,也是那串 discussion 的標題

_WISH_QUERY = """
{ repository(owner:"yazelin", name:"neko-tensei") {
    discussions(first:20, orderBy:{field:UPDATED_AT, direction:DESC}) {
      nodes { title category { name } comments(first:100) { nodes { body } } } } } }
"""


def load_canon():
    """讀出 LLM 寫企劃需要知道的一切。"""
    cfg = json.loads((ROOT / 'episodes.json').read_text('utf-8'))
    eps = cfg['episodes']
    ordered = sorted(eps, key=lambda e: e['n'])
    rules = (ROOT / 'story' / 'README.md').read_text('utf-8')
    recent = "\n\n".join(
        (ROOT / 'story' / f"ep{e['n']}.md").read_text('utf-8')
        for e in ordered[-2:]
        if (ROOT / 'story' / f"ep{e['n']}.md").is_file())
    if not recent.strip():
        raise RuntimeError(
            '讀不到任何一話的分鏡(story/epN.md),LLM 會完全沒有前情提要。'
            '這條 pipeline 的價值就在連續性,寧可停下來也不要產一話接不上的東西。')
    return {
        'next_n': ordered[-1]['n'] + 1,
        'episodes': eps,
        'rules': rules,
        'recent': recent,
    }


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
    """讀首頁許願串。

    回 (許願清單, 失敗原因)。

    「還沒有人許願」是正常狀態,不是錯誤——giscus 要等第一則留言才會建
    discussion,所以第一週一定是空的,回 ([], None)。
    但「gh 沒認證 / API 壞了」是真的該讓人知道的,回 ([], '原因'),
    呼叫端才能把它寫進 PR 內文,而不是靜靜當成「這次沒有許願」。
    """
    try:
        r = subprocess.run(['gh', 'api', 'graphql', '-f', f'query={_WISH_QUERY}'],
                           capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            return [], f'gh api graphql 失敗: {r.stderr.strip()[:200]}'
        return parse_wishes(json.loads(r.stdout)), None
    except Exception as e:                      # noqa: BLE001 - 許願是加分項,不該擋住出稿
        return [], f'{type(e).__name__}: {e}'


CHARS = {'xiaoniao', 'xiaobai', 'uncle', 'leo', 'kojiro'}

_SIMPLIFIED_MAP = None
_TW_STANDARD = None


def _simplified_map():
    """OpenCC 自帶的簡轉繁字元對照表(字元級),初始化要讀字典檔,只做一次。

    直接讀 opencc 套件內附的 STCharacters.txt,不手key任何一份表——那是
    OpenCC 自己維護的資料,我們只是換一種讀法。
    """
    global _SIMPLIFIED_MAP
    if _SIMPLIFIED_MAP is None:
        import opencc
        path = pathlib.Path(opencc.__file__).parent / 'dictionary' / 'STCharacters.txt'
        m = {}
        for line in path.read_text('utf-8').splitlines():
            if not line.strip():
                continue
            simp, cands = line.split('\t')
            m[simp] = cands.split()
        _SIMPLIFIED_MAP = m
    return _SIMPLIFIED_MAP


def _tw_variants():
    """OpenCC 自帶的「異體字 → 台灣標準字」對照表,同樣只在第一次呼叫讀檔。

    讀 opencc 套件內附的 TWVariants.txt。key 是異體字(如「峯」),value 是
    台灣教育部標準寫法(如「峰」)。跟 STCharacters.txt 一樣,不手key任何
    一份表。
    """
    global _TW_STANDARD
    if _TW_STANDARD is None:
        import opencc
        path = pathlib.Path(opencc.__file__).parent / 'dictionary' / 'TWVariants.txt'
        m = {}
        for line in path.read_text('utf-8').splitlines():
            if not line.strip():
                continue
            variant, standard = line.split('\t')
            m[variant] = standard
        _TW_STANDARD = m
    return _TW_STANDARD


TW_EXTRA = {
    # 放行表,不是封鎖表——這條紅線是「不要手維護『什麼算簡體』的表」,
    # 因為封鎖表寫錯一個字會大規模誤殺(「那」幾乎每句話都有,差點讓驗證器
    # 變成全擋合法企劃)。這份表方向相反:漏收一個字,代價只是漏掉一個
    # 簡體字沒被擋下來,而 PR 是人工審查才會合併的,人看得見。失效方向不
    # 對稱,所以可以承受比較低的舉證門檻,但還是要收得謹慎:
    #   1. 只收「OpenCC 隨附字典檔(STCharacters/TWVariants/TWPhrases/
    #      HKVariants 等)都救不到」的字——能靠 _tw_variants() 放行的不要
    #      往這裡加,加了也是重複。
    #   2. 每一筆都要附外部權威來源(字典網址),不能只憑印象。
    #   3. 新增前務必用 test_台灣標準異體字要放行 之類的回歸測試逐字鎖住,
    #      並用 test_TW_EXTRA不能收真正的簡體字 這條反向測試過一次。
    '霉': ('教育部《重編國語辭典修訂本》收「霉」「霉頭」「發霉」「倒霉」為'
           '正式詞條,是台灣教育部承認的用字,只有「黴菌」固定用「黴」。'
           'STCharacters.txt 只收「霉→黴」,TWVariants.txt 沒有這對資料,'
           '兩邊都救不到才進這裡。'
           'https://dict.revised.moe.edu.tw/dictView.jsp?ID=1124'),
}


def has_simplified(text):
    """回第一個簡體字;都是正體就回 None。

    **不要手維護字表**。這份計劃原本為了省掉相依而手打了一份 231 字的表,
    派工前實測發現裡面混進正體字——那、只、巨、唯、反、埋、准。「那」幾乎
    每句話都有,那份表會把絕大多數合法企劃當成含簡體字擋掉,而且錯得很安靜。

    改用 OpenCC 之後第一版是整段跑 s2t 再逐字比對,結果一樣誤殺:OpenCC 的
    詞組字典(STPhrases)會把「回流」「注定」等本來就是合法正體的用字,
    校正成它認為更正統的「迴流」「註定」,連自己已經上線的對白(story/ep2.md
    裡的「里歐」「回流」)都會被判成簡體。問題出在詞組層級的上下文校正,
    不是字元本身。改成只查字元級的 STCharacters.txt:一個字只要出現在它
    自己的候選清單裡(例如「里」的候選是「裏 里」),代表它本來就有合法的
    正體用法(當人名「里歐」時),就不算簡體;只有候選清單完全不含自己的
    字(例如「这」的候選只有「這」),才是真正只能是簡體的字。

    這個字元級判斷後來又發現一個洞:STCharacters.txt 收了一批「異體字
    正規化」,不是真的簡繁對立——例如「峰」的候選只有「峯」,照上面的規則
    「峰」會被誤判成簡體,但「峰」其實才是台灣教育部標準寫法(「峯」是
    異體字)。同類還有「床/牀」「灶/竈」「痴/癡」「秘/祕」「粽/糉」
    「群/羣」,全表掃描確認只有這 7 個字受影響。修法是再查一次
    TWVariants.txt:候選字裡如果有誰的台灣標準寫法就是 ch 自己,代表 ch
    本身就是台灣慣用字,放行。

    TWVariants.txt 不是萬能的:「霉」(教育部辭典承認的台灣用字,只有
    「黴菌」固定用「黴」)這對資料兩邊字典檔都沒收,確認過所有 OpenCC
    隨附字典檔都救不到之後,才另外開了 TW_EXTRA 這份小的放行表——每一筆
    都要附權威來源,細節見 TW_EXTRA 的註解。

    已知假陰性(接受的 trade-off,不是 bug):字元級判斷完全不看上下文,
    只要一個字的候選清單裡包含它自己(代表它有合法的正體用法),就永遠
    放行那個字——即使整句話其實是簡體。例如「里」的候選含「里」本身
    (人名「里歐」時是正體),所以『你在里面嗎?』『我躲在后面』這種整句
    都是簡體的句子也會回 None,因為每個字單獨看都「可能」是正體。「只」
    「干」「面」「后」「厂」「表」「注」都有同樣的洞。這條線要擋的是
    LLM 出企劃時偶爾夾帶的簡體字,不是抓故意寫的整段簡體文,這個 trade-off
    在這個用途下可以接受,但要記錄下來讓後面的人知道邊界在哪。
    """
    if not text:
        return None
    m = _simplified_map()
    tw = _tw_variants()
    for ch in text:
        cands = m.get(ch)
        if not cands or ch in cands:
            continue
        if any(tw.get(c) == ch for c in cands):
            continue
        if ch in TW_EXTRA:
            continue
        return ch
    return None


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

    `next_n`(下一話話數)目前沒有被本函式用到——保留是為了配合設計文件
    訂下的介面,呼叫端(main)本來就會傳。頁碼本身是用固定的 01~06 這組
    範圍驗證,不需要依賴 next_n 才能檢查;如果之後要加「封面上的話數字樣
    要對上 next_n」之類的規則,這個參數已經在這裡,不用再改函式簽名。
    """
    errs = []
    if not isinstance(plan, dict):
        return ['企劃不是一個物件']

    for field in ('title', 'desc', 'beats', 'pages'):
        value = plan.get(field)
        if isinstance(value, str):
            value = value.strip()
        if not value:
            errs.append(f'缺欄位:{field}')
    if errs:
        return errs

    if plan['title'] in (titles or []):
        errs.append(f'標題與既有話數重複:{plan["title"]}')

    pages = plan['pages']
    if len(pages) != 6:
        errs.append(f'內頁必須六頁,拿到 {len(pages)} 頁')

    # 頁碼必須是 01~06 各一次,不能重複也不能亂編——重複的話同一頁會被
    # 出兩張圖或漏掉別頁,順序錯了 build.py 排版會照檔名排,話就亂了。
    page_ns = [pg.get('n') for pg in pages]
    if set(page_ns) != {f'{i:02d}' for i in range(1, 7)} or len(page_ns) != len(set(page_ns)):
        errs.append(f'頁碼必須是 01~06 各一次不重複,拿到:{page_ns}')

    for pg in pages:
        n = pg.get('n')
        if not pg.get('panels'):
            errs.append(f'第 {n} 頁沒有分格')
            continue
        for c in pg.get('chars') or []:
            if c not in CHARS:
                errs.append(f'第 {n} 頁出現不認識的角色:{c}')
        # world 是選配欄位,但寫了就必須是 cast.json 裡真的有設定圖的 id——
        # 打錯字會被 page_refs 靜靜忽略,那一格就退回沒有鎖的狀態,結果是圖
        # 漂了卻沒有任何地方報錯。
        for w in pg.get('world') or []:
            if w not in prompt.WORLD_KEYS:
                errs.append(f'第 {n} 頁指名了不存在的道具/場景:{w}'
                            f'(可用的:{"、".join(prompt.WORLD_KEYS) or "無"})')

        page_shapes = []
        page_lines = 0
        for _n, speaker, shape, text in _lines({'pages': [pg]}):
            page_lines += 1
            if not (text or '').strip():
                errs.append(f'第 {n} 頁有空白對白')
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
        elif page_shapes and len(set(page_shapes)) < 2 and page_lines > 1:
            # page_shapes 可能是空的(整頁的框型都不存在,上面已經逐句報過
            # 錯了),空清單不能再拿 [0] 出來比,不然驗證器自己會 crash——
            # 這是最不該發生的地方:守門員在最該擋的時候死掉。
            errs.append(f'第 {n} 頁的框型全部一樣({page_shapes[0]}),框型要跟著情緒走')

    return errs


# 用 `or` 不用 get 的第二參數:workflow 把 ${{ secrets.X }} 塞進 env 時,
# secret 不存在給的是空字串而不是「沒這個變數」,get 的預設值救不到,
# base url 會變成 '' 讓 URL 組成 /v1beta/... 直接炸在 CI 上。
GEMINI_BASE = os.environ.get('GEMINI_WEB_BASE_URL') or 'https://ching-tech.ddns.net/gemini-web'
GEMINI_MODEL = os.environ.get('GEMINI_MODEL') or 'gemini-2.5-flash'

_PLAN_SHAPE = """{
  "title": "不含「第N話」三個字的標題",
  "kind": "推進主線 | 日常番 | 烏龍 | 角色刻畫",
  "desc": "一到兩句,給網站 meta description 用",
  "beats": ["轉折一", "轉折二", "轉折三"],
  "pages": [
    { "n": "01",
      "chars": ["出場角色的 slug"],
      "world": ["這一頁畫面上出現的道具/場景 id,沒有就給空陣列"],
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


def _world_hint():
    """把 cast.json 的道具/場景翻成 id=中文名,讓編劇知道每個 id 是什麼東西。"""
    w = prompt._CAST.get('world', {})
    return '、'.join(f'{k}={v["name"]}' for k, v in w.items()) or '無'


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
- `world` 只能填這些 id：{' / '.join(prompt.WORLD_KEYS) or '（目前沒有）'}
  （{_world_hint()}）
  **畫面上看得到那樣東西的每一頁都要填**，這是它不跑樣的唯一依據；沒出現就給空陣列
- **同一頁的框型不可以全部一樣**，框型要跟著情緒走
- 對白一律正體中文（台灣用語），一頁 3 到 6 句，句子不要長
- kojiro 不可以用 THOUGHT 框，他沒有前世可以浮出來
- 標題不可以跟既有話數重複
- **`scene` 裡的動作要用手做**。這五隻是擬人化的貓，站著、有手、會拿東西——
  拔插頭就用手拔，不要寫「用貓牙咬住電纜扯出來」「用後腿把電纜踢回插座」。
  第三話第 04 頁就是這樣出事的：模型很聽話地照畫，姿勢卡在中間，人看一眼
  就知道不對。真要用嘴或用腳，得是刻意的笑點，而且要跟角色個性對得上
  （小鳥不啾是冷靜吐槽型，不會又咬又踢）"""


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
    try:
        return payload['candidates'][0]['content']['parts'][0]['text']
    except (KeyError, IndexError):
        # 常見成因:內容被安全機制擋掉(這部漫畫有戰鬥、魔王、「四隻空瓶子」
        # 這種挑釁台詞,撞到安全機制是真的會發生的情況,不是罕見邊角案例)、
        # candidates 是空 list、或整包格式跟預期不一樣。原生的 KeyError/
        # IndexError 只會指出「哪個鍵/索引不存在」,追蹤時分不出是被擋了還是
        # API 本身出錯,所以把 finishReason / promptFeedback(如果有)與整包
        # payload 的前 300 字一起帶出來。
        candidates = payload.get('candidates') if isinstance(payload, dict) else None
        candidates = candidates or []
        finish_reason = candidates[0].get('finishReason') if candidates else None
        prompt_feedback = payload.get('promptFeedback') if isinstance(payload, dict) else None
        raise RuntimeError(
            'gemini-web 回應裡沒有可用的文字內容'
            '(取不到 candidates[0].content.parts[0].text)。'
            f' finishReason={finish_reason!r} promptFeedback={prompt_feedback!r}'
            f' payload 前 300 字:{json.dumps(payload, ensure_ascii=False)[:300]}') from None


def make_plan(canon, wishes):
    text = call_llm(build_planner_prompt(canon, wishes))
    try:
        return json.loads(_strip_fence(text))
    except json.JSONDecodeError as e:
        # 拿掉包裝直接讓 JSONDecodeError 往外丟,追蹤只看得到「哪個字元解析
        # 失敗」,看不到 LLM 實際回了什麼——這裡把原文前 300 字帶出來,才
        # 查得出是圍籬沒拆乾淨還是 LLM 真的沒照格式回。
        raise RuntimeError(
            f'LLM 回傳的不是合法 JSON:{e}。實際回傳內容前 300 字:{text[:300]}') from None


IMG_BASE = os.environ.get('CODEX_IMAGE_BASE_URL') or 'https://ching-tech.ddns.net/codex-image'
SPEAKER_REF = {'xiaoniao': 'xiaoniao', 'xiaobai': 'xiaobai',
               'uncle': 'uncle', 'leo': 'leo', 'kojiro': 'kojiro'}
POS_LABEL = {'top': 'top', 'mid': 'middle', 'middle': 'middle', 'bottom': 'bottom'}


def page_body(page):
    """把企劃的一頁翻成給繪圖模型看的 PANEL 段落。

    `scene`/`shape`/`text` 三個欄位缺任何一個都要炸,而且錯誤要指得出是
    第幾頁第幾格——這支之後在 GitHub Actions 無人值守跑,裸 KeyError 在
    log 裡跟其他 bug 分不出來;`scene` 缺欄位又特別危險,原本是靜默印出
    `PANEL 1 (top): `(空場景)不報錯也不留痕跡,會默默組出一份沒有畫面
    描述的 prompt,花掉一次出圖額度產一張沒人要的圖。
    """
    n = page.get('n', '?')
    out = []
    for i, pn in enumerate(page.get('panels') or [], 1):
        where = f'第 {n} 頁第 {i} 格'
        scene = pn.get('scene')
        if not (scene or '').strip():
            raise ValueError(f'{where}缺 scene')
        pos = POS_LABEL.get(pn.get('pos'), pn.get('pos') or '')
        out.append(f"PANEL {i} ({pos}): {scene}")
        for ln in pn.get('lines') or []:
            shape = ln.get('shape')
            if not (shape or '').strip():
                raise ValueError(f'{where}缺 shape')
            text = ln.get('text')
            if not (text or '').strip():
                raise ValueError(f'{where}缺 text')
            kind = 'CAPTION BOX' if shape == 'CAPTION' else f"{shape} BALLOON"
            who = SPEAKER_REF.get(ln.get('speaker'), ln.get('speaker') or '')
            out.append(f"  {kind} from {who}: {text}")
    return "\n".join(out)


# 參考圖張數上限。codex-image-service 的 API 本身沒有張數限制,真正的限制
# 是稀釋:塞太多張,特徵會開始互相污染。8 是 comic-studio 實測的上限。
MAX_REFS = 8


def page_refs(page):
    """該頁要傳哪幾張參考圖,依優先序排。

    優先序:畫風錨 → 這一格要鎖的道具/場景 → 出場角色的設定圖 → 前世。
    道具排在角色前面是因為它決定這一格長什麼樣;而且被上限截掉時,先被丟掉的
    應該是排最後的補充圖,不是鎖。通行證就是漂在沒有這一層的時候——它沒有
    自己的設定圖,整頁 prompt 裡對它唯一的描述還是錯的。

    有 THOUGHT 框代表畫面上會有前世的記憶泡,那就要多帶前世設定圖——
    只給文字描述的話四個人全會畫錯。
    """
    keys = ['style']
    for w in page.get('world') or []:
        if w in prompt.WORLD_KEYS and w not in keys:
            keys.append(w)
    for c in page.get('chars') or []:
        k = SPEAKER_REF.get(c)
        if k and k not in keys:
            keys.append(k)
    has_os = any(ln.get('shape') == 'THOUGHT'
                 for pn in page.get('panels') or []
                 for ln in pn.get('lines') or [])
    if has_os and 'past' not in keys:
        keys.append('past')
    # 框型對照圖排在畫風錨後面,但只有還有空位才放——它是手法的錨,角色設定圖
    # 與前世灰階是內容正確性,兩者搶額度時先保內容。所以它是唯一一個「擠不下
    # 就不放」的參考圖,而不是把別人擠掉。
    if len(keys) < MAX_REFS:
        keys.insert(1, 'balloons')
    return keys[:MAX_REFS]


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


def _cell(s):
    """markdown 表格欄位值裡的 `|` 要轉成 `\\|`,不然會被當成分欄符號,
    把整列切成錯的欄數——這部漫畫角色是工程師,對白出現 `|` 不是罕見情況。
    換行也順手換成空格,原因一樣:換行在表格列裡會直接把那一列切斷。
    """
    return (s or '').replace('|', '\\|').replace('\n', ' ')


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
                out.append(f"| {_cell(pos)} | {_cell(scene)} | "
                           f"{_cell(NAME.get(ln['speaker'], ln['speaker']))}"
                           f"「{_cell(ln['text'])}」 | {_cell(ln['shape'])} |")
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


def pr_body(plan, n, wishes, wish_err=None, branch=None):
    """組 PR 內文。

    `wish_err` 是 `fetch_wishes()` 回傳 tuple 的第二個值——「讀許願失敗」
    跟「這次沒有人許願」是兩種完全不同的狀態,絕對不能混在一起顯示成同一句
    「這次沒有許願」:社群如果真的寫了許願,只是這次讀取本身出錯(gh 沒
    認證、API 壞掉……),顯示成「沒有許願」等於把那些許願直接吃掉,而且
    沒有人會知道出過事。`wish_err` 非 None 時必須明講「讀許願失敗」與
    原因,不能落到「沒有許願」那個分支。

    `branch` 是這份草稿所在的分支(workflow 裡是 `auto/ep{n}`)。這一話的
    新圖只存在這個尚未合併的分支上,main 上還沒有——圖片連結絕對不能用
    `blob/HEAD/…`,那會解析成預設分支(main),連到的是不存在的檔案。
    這條 pipeline 的整個設計就是「人看圖、按 merge」,圖是壞連結,人工
    審查就等於在看不到要審的東西的情況下按 merge,閘門形同虛設。改用
    `raw.githubusercontent.com/{branch}/…`——直接指到分支上的原始檔案,
    不會被 GitHub markdown 的相對路徑規則影響。
    """
    branch = branch or f'auto/ep{n}'
    kind = plan.get('kind') or '推進主線'
    if wish_err is not None:
        wish_line = f"讀許願失敗，不是沒有人許願：{wish_err}"
    elif wishes:
        wish_line = f"讀了 {len(wishes)} 則社群許願"
    else:
        wish_line = "這次沒有許願，由 AI 自己決定要畫什麼"
    out = [f"# 第{_zh(n)}話：{plan['title']}\n",
           f"**話型：{kind}**　" + wish_line + '\n',
           plan['desc'] + '\n', '## 三個轉折\n']
    out += [f'{i}. {b}' for i, b in enumerate(plan['beats'], 1)]
    if wish_err is not None:
        out.append('\n## 許願讀取失敗\n')
        out.append(f'- {wish_err}')
        out.append('\n社群這次可能真的有許願，但這一版沒讀到——'
                   '合併前請人工查一下許願串，必要的話重跑一次。\n')
    elif wishes:
        out.append('\n## 這次讀到的社群許願\n')
        out += [f'- {w}' for w in wishes]
    out.append('\n## 逐頁對照\n')
    out.append('**你要看的不是劇情，是圖有沒有照劇本畫。** '
               '劇情在文字層通常沒問題，會出事的是「劇本寫的」跟「圖畫出來的」之間那道縫——'
               '第二話里歐的「隱形只隱一半」就是分鏡完全正確、圖卻畫成一隻完整的橘貓，'
               '整頁的笑點沒了，而讀分鏡檔案完全看不出來。\n')
    for pg in plan['pages']:
        out.append(f"\n### 第 {pg['n']} 頁\n")
        out.append(f"![第 {pg['n']} 頁]"
                   f"(https://raw.githubusercontent.com/yazelin/neko-tensei/{branch}"
                   f"/images/ep{n}/{pg['n']}.webp)\n")
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


WEBP_QUALITY = 95


def save_image(raw, out):
    """把服務端回來的位元組重新壓成 webp 再落檔。

    服務端回的是接近無損的 webp,一頁 3.7 MB。第一次真跑的第三話因此是
    23 MB,而手工做的第一話 3.5 MB、第二話 4.7 MB——五倍重。q95 重壓後
    一頁 0.88 MB,平均像素差 2.5/255,放大看對白仍然銳利。

    這個站是 PWA,全部圖檔都會被 precache,`sw.js` 的 ASSET 版號一 bump,
    回訪讀者就整包重抓。一話 23 MB 跟一話 5 MB 是完全不同的體驗,而且
    每加一話就疊上去一次。
    """
    if out.suffix.lower() != '.webp':
        out.write_bytes(raw)
        return
    import io
    from PIL import Image
    Image.open(io.BytesIO(raw)).convert('RGB').save(out, 'WEBP', quality=WEBP_QUALITY)


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
    job_id = job.get('id')
    if not job_id:
        # 裸 KeyError 只看得出「id 不在」,看不出服務實際回了什麼——這裡
        # 跟 call_llm 的畸形回應處理一樣,把回應前 300 字帶出來方便追蹤。
        raise RuntimeError(
            f'{name} 出圖失敗:建立 job 的回應沒有 id。'
            f' 回應前 300 字:{json.dumps(job, ensure_ascii=False)[:300]}')
    print(f'  job {name} {job_id}', flush=True)

    t0 = time.time()
    while True:
        time.sleep(15)
        q = urllib.request.Request(f'{IMG_BASE}/v1/images/jobs/{job_id}',
                                   headers={'Authorization': hdr['Authorization']})
        with urllib.request.urlopen(q, timeout=60) as f:
            st = json.load(f)
        if st['status'] in ('succeeded', 'failed', 'error'):
            break
        if time.time() - t0 > 2400:
            raise RuntimeError(f'{name} 出圖逾時')
    if st['status'] != 'succeeded':
        raise RuntimeError(f'{name} 出圖失敗: {str(st.get("error"))[:200]}')

    images = st.get('images')
    if not images or not images[0].get('url'):
        raise RuntimeError(
            f'{name} 出圖失敗:狀態是 succeeded 但回應沒有 images。'
            f' 回應前 300 字:{json.dumps(st, ensure_ascii=False)[:300]}')
    url = images[0]['url']
    if url.startswith('/'):
        url = IMG_BASE + url
    out.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=300) as r:
        save_image(r.read(), out)
    print(f'  -> {name} ok {int(time.time() - t0)}s '
          f'{out.stat().st_size / 1e6:.2f}MB', flush=True)


IMG_RETRIES = 3


SERIES_TITLE = '轉生成貓貓的我們'


def cover_body(plan, n):
    """封面的畫面描述,含標題、角色名牌與底部話數帶。

    pipeline 一開始刻意讓封面完全無字,理由是「文字烤進圖裡,改一個字就是整張
    重生」。那個理由本身沒錯,但它沒看既有封面長什麼樣——第一、二話的標題就是
    AI 畫進去的(story/README.md 有一整段在講外稿封面的錯字怎麼修,會有錯字正
    代表那些字是模型畫的),結果第三話變成整個系列裡唯一沒標題的封面。所以改回
    烤字,並把第二話封面當參考圖鎖版面。

    代價要認:中文字可能出錯,每次改字要整張重生,出稿後必須逐字校對。錯字的
    修法在 story/README.md——像素級補字之後還要再丟回去重繪一次。

    開頭那句反指令是要壓掉 prompt.BASE 寫死的「THREE horizontal panels」——
    封面是單張圖,而 body 排在整份 prompt 最後面,才蓋得掉前面的分鏡指令。
    """
    beats = '; '.join(plan.get('beats') or [])
    tags = '、'.join(f'「{v}」' for v in NAME.values())
    band = f"第{_zh(n)}話：{plan.get('title', '')}"
    return (f"A single dramatic cover illustration, NOT a multi-panel page.\n"
            f"All five cats together in one heroic group composition: the MAGE CAT, "
            f"the SWORDSMAN CAT, the SAMURAI CAT, the ROGUE CAT, and looming behind them "
            f"the DEMON KING CAT.\n"
            f"The mood and setting come from this episode: {plan.get('desc', '')}\n"
            f"Key moments of the episode, use them to choose the setting and lighting: {beats}\n"
            f"LAYOUT AND LETTERING - copy the layout of reference image 2 exactly:\n"
            f"- The series title 「{SERIES_TITLE}」 across the upper half in two lines, "
            f"large chunky hand-drawn Chinese display type, thick gold outline, dark drop "
            f"shadow, the two characters 貓貓 in bright pink and the rest in near-black, "
            f"with a few small paw-print marks tucked around the letters.\n"
            f"- One small dark rounded name tag beside each cat, each with a little paw icon "
            f"and that cat's name: {tags}. Put each tag next to the cat it names.\n"
            f"- A slim band along the very bottom edge with a paw icon and the text "
            f"「{band}」.\n"
            f"Portrait aspect ratio 2:3, same painterly vibrant anime fantasy style as "
            f"reference image 1.")


def cover_refs(plan):
    """封面的參考圖:畫風錨 → 這一話出現過的道具/場景 → 五位角色。

    道具鎖排在角色前面、而且非帶不可——第三話第一次真跑時封面沒帶任何道具
    鎖,通行證被畫成一張紅色長方形門禁卡(內頁那張則畫成金懷錶,兩張各漂
    各的)。封面通常是最多人看到的一張,不能是唯一沒上鎖的那張。

    上限一樣是 MAX_REFS。角色排最後,因為封面本來就要五位全到,萬一道具多
    到擠掉角色,那是企劃該收斂,不是這裡該偷偷丟掉鎖。
    """
    keys = ['style', 'cover_style']
    for pg in plan.get('pages') or []:
        for w in pg.get('world') or []:
            if w in prompt.WORLD_KEYS and w not in keys:
                keys.append(w)
    keys += ['xiaoniao', 'xiaobai', 'uncle', 'leo', 'kojiro']
    return keys[:MAX_REFS]


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
        if not m:
            raise RuntimeError(f'sw.js 找不到 nt-{kind}-v<數字>,版號沒 bump 就落檔會讓'
                               f'讀者拿到舊快取,這裡直接停下來')
        t = t.replace(m.group(0), f"nt-{kind}-v{int(m.group(1)) + 1}")
    sw.write_text(t, 'utf-8')

    subprocess.run(['python3', str(ROOT / 'build.py')], check=True, cwd=ROOT)


CACHE = ROOT / '.pipeline-cache'


def _plan_cache(n):
    return CACHE / f'ep{n}-plan.json'


def load_cached_plan(n):
    """上一次沒跑完留下的企劃。沒有、或檔案壞掉,都回 None。

    壞掉當作沒有而不是丟例外:上一次可能是跑到一半被砍,檔案只寫了一半。
    那種時候該重出一份企劃,不是讓整條線倒在讀快取這一步。
    """
    p = _plan_cache(n)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text('utf-8'))
    except (json.JSONDecodeError, OSError):
        print(f'快取的企劃讀不動,當作沒有:{p}')
        return None


def save_cached_plan(n, plan):
    CACHE.mkdir(parents=True, exist_ok=True)
    _plan_cache(n).write_text(json.dumps(plan, ensure_ascii=False, indent=2), 'utf-8')


def clear_cached_plan(n):
    _plan_cache(n).unlink(missing_ok=True)


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
        errs = validate_plan(plan, n, titles)
        if errs:
            print('企劃沒過驗證:')
            for e in errs:
                print(' -', e)
            return 1
    elif (cached := load_cached_plan(n)) and not a.plan_only:
        # 上一次跑到一半掛掉。沿用同一份企劃,不然新劇本會配到舊圖。
        plan = cached
        print('沿用上次沒跑完的企劃:', plan.get('title'))
    else:
        try:
            plan = plan_with_retry(canon, wishes, titles, n)
        except RuntimeError as e:
            print(e)
            return 1
        if not a.dry_run and not a.plan_only:
            save_cached_plan(n, plan)
        if a.plan_only:
            pathlib.Path(a.plan_only).write_text(
                json.dumps(plan, ensure_ascii=False, indent=2), 'utf-8')
            print('企劃已存到', a.plan_only)
            return 0
    print('企劃通過驗證:', plan['title'])

    if a.dry_run:
        return 0

    cover_path = ROOT / f'images/ep{n}/00-cover.webp'
    if not a.skip_images:
        # 社群投稿的封面永遠優先:已經有檔案就不要蓋掉
        if not cover_path.is_file():
            generate_with_retry('cover', cover_refs(plan), cover_body(plan, n), cover_path)
        else:
            print('封面已存在,跳過(社群投稿優先)')
        for pg in plan['pages']:
            out = ROOT / f'images/ep{n}' / f"{pg['n']}.webp"
            if out.is_file():
                # 上一次跑到一半留下來的。整話七張約 36 分鐘,不要從第一張重來。
                print(f'  {pg["n"]} 已存在,跳過', flush=True)
                continue
            generate_with_retry(pg['n'], page_refs(pg), page_body(pg), out)
    has_cover = cover_path.is_file()

    publish(plan, n, has_cover)
    (ROOT / f'.pr-body-ep{n}.md').write_text(pr_body(plan, n, wishes, wish_err), 'utf-8')
    clear_cached_plan(n)          # 落檔成功,這一話的續傳狀態不再需要
    print('落檔完成。PR 內文在 .pr-body-ep%d.md' % n)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
