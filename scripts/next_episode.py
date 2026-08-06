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
import mimetypes
import os
import pathlib
import re
import subprocess
import sys
import time
import urllib.request
import zoneinfo

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

# slug → scene 描述裡用的英文代號(cast.json 的 desc 就是 "MAGE CAT model sheet"
# 這種形狀,去掉尾巴的 model sheet 就是代號)。生圖端讀的是 scene 那段英文,
# 對白的 speaker 只是標籤,所以「誰在畫面上」完全由 scene 決定。
# 四位主角。小次郎是魔王,不算在「四貓」裡。
FOUR_CATS = ('xiaoniao', 'xiaobai', 'uncle', 'leo')

# 群像格的說法。scene 這樣寫就代表四貓都在畫面上,不必逐一點名。
GROUP_PHRASES = ('ALL FOUR CATS', 'FOUR CATS', 'THE FOUR HEROES', 'ALL FIVE CATS',
                 'FIVE CATS')

CHAR_TAGS = {
    slug: (prompt._CAST['cast'][slug]['desc'].split(' model sheet')[0].strip())
    for slug in ('xiaoniao', 'xiaobai', 'uncle', 'leo', 'kojiro')
    if slug in prompt._CAST.get('cast', {})
}

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

    # 異世界元素必填,而且要真的是異世界的東西。
    #
    # 光在 prompt 裡要求沒有用:第二話到第六話連續五話的舞台都是機房,而
    # planner prompt 會把「最近兩話的分鏡」整段餵進去要它接得上——文字要求
    # 打不過示範。改成必填欄位,模型至少得**明說**這一話的異世界元素是什麼,
    # 而且人在 PR 上看得到它填了什麼。
    fantasy = (plan.get('fantasy') or '').strip()
    if not fantasy:
        errs.append('缺欄位:fantasy(這一話畫面上真的會出現的異世界元素)')
    elif not any(c.isalpha() for c in fantasy):
        errs.append(f'fantasy 要寫一句英文,拿到:{fantasy}')
    else:
        banned = [w for w in FANTASY_BANNED if w in fantasy.lower()]
        if banned:
            errs.append(f'fantasy 填的是機房那一類的東西({"、".join(banned)}):{fantasy}'
                        '。要的是怪物、魔法戰鬥、地形、村民 NPC 這種只有異世界才有的')

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

        # 有台詞的角色一定要出現在該格的 scene 裡。
        #
        # 第六話第 02 頁第一格就是這樣壞的:scene 只寫了 ROGUE CAT,卻掛著中年
        # 攻城屍的台詞,SAMURAI CAT 從頭到尾沒被提到——生圖端讀的是 scene 那段
        # 英文,speaker 只是給人看的標籤,所以模型只好自己補一隻,補成了小鳥不啾。
        # 同一話六頁裡有四頁犯這個錯。這條是純字串比對,擋在出圖之前,零成本。
        for panel in pg.get('panels') or []:
            scene = (panel.get('scene') or '')
            speakers = {ln.get('speaker') for ln in (panel.get('lines') or [])}
            # 別名:企劃常寫 "KOJIRO holographic projection" 而不是完整的
            # "DEMON KING CAT"。角色確實被點名了,純字串比對太死會退掉好企劃。
            upper = scene.upper()
            # 群像格:"all four cats standing together" 四貓都在畫面上,只是沒
            # 逐一點名。這是合法寫法,不該被擋。小次郎不在「四貓」裡,他要另外
            # 點名。
            grouped = any(g in upper for g in GROUP_PHRASES)
            missing = sorted(
                CHAR_TAGS[sp] for sp in speakers
                if sp in CHAR_TAGS
                and CHAR_TAGS[sp] not in scene
                and sp.upper() not in upper
                and not (grouped and sp in FOUR_CATS)
            )
            if missing:
                errs.append(
                    f'第 {n} 頁有格子讓「{"、".join(missing)}」說話,但畫面描述裡'
                    f'沒有他:{scene[:80]}')

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

# 企劃(寫劇本)走哪個後端。預設 gemini,fork 的人把 PLANNER_PROVIDER 設成
# openai 就能改用任何 OpenAI 相容端點(OpenAI 本尊、Groq、Ollama、OpenRouter),
# 差別只有 OPENAI_BASE_URL 跟模型名。gemini 這條也不綁我的中繼:把
# GEMINI_WEB_BASE_URL 指到 https://generativelanguage.googleapis.com
# 就是官方端點,腳本組出來的路徑本來就是官方那個形狀。
# 所有對外請求都要帶 User-Agent。Groq 擋在 Cloudflare 後面,看到 urllib 的預設
# UA(Python-urllib/3.x)直接回 403 error code 1010,而那個回應裡沒有任何字說
# 是 UA 的問題,只會看起來像金鑰壞了。實測:換成任何自訂 UA 就通。
UA = 'neko-tensei-pipeline/1 (+https://github.com/yazelin/neko-tensei)'

PLANNER_PROVIDER = (os.environ.get('PLANNER_PROVIDER') or 'gemini').lower()
OPENAI_BASE = os.environ.get('OPENAI_BASE_URL') or 'https://api.openai.com/v1'
OPENAI_MODEL = os.environ.get('OPENAI_MODEL') or 'gpt-4o-mini'
OPENAI_MAX_TOKENS = int(os.environ.get('OPENAI_MAX_TOKENS') or 32768)

_PLAN_SHAPE = """{
  "title": "不含「第N話」三個字的標題",
  "kind": "推進主線 | 日常番 | 烏龍 | 角色刻畫",
  "desc": "一到兩句,給網站 meta description 用",
  "fantasy": "這一話畫面上真的會出現的異世界元素,一句英文。怪物/魔法戰鬥/地形/村民 NPC/非現實道具都算;螢幕、主機房、全像投影、程式碼不算",
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


# fantasy 欄位不可以填這些——它們正是這部作品已經寫到爛的那一類。
FANTASY_BANNED = ('server', 'hologram', 'holographic', 'screen', 'console',
                  'terminal', 'code', 'commit', 'merge', 'pull request',
                  'dashboard', 'keyboard', 'monitor', 'data center')

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


def build_planner_prompt(canon, wishes, previous_errors=None):
    wish_block = ("社群這次的許願（要盡量收進去，收不進去的就留給以後）：\n"
                  + "\n".join(f'- {w}' for w in wishes)) if wishes else \
        '這次沒有社群許願，由你自己決定要畫什麼。'
    retry_block = ''
    if previous_errors:
        retry_block = ('\n\n你上一版沒過驗證,以下每一條都要修掉再交:\n'
                       + '\n'.join(f'- {e}' for e in previous_errors)
                       + '\n這些不是建議,是硬性規則。修的時候不要只補一格,'
                         '整份重看一遍有沒有同類問題。')
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
- **每一格的 `scene` 必須點名這一格所有說話的角色,並寫出他們在畫面的位置。**
  用英文代號:xiaoniao=MAGE CAT、xiaobai=SWORDSMAN CAT、uncle=SAMURAI CAT、leo=ROGUE CAT、kojiro=DEMON KING CAT。位置用相對詞(left / center / right / foreground /
  behind)。生圖端讀的是 `scene` 那段英文,`speaker` 只是給人看的標籤——沒被
  `scene` 提到的角色,模型會自己補一隻,而它補出來的通常是別人。第六話六頁裡
  有四頁犯這個錯,「老夫」的台詞連續被畫給戴眼鏡的小鳥不啾。
  寫成「SAMURAI CAT stands at the right, hands raised in panic, while ROGUE CAT
  types at the left」這種,不要只寫一隻然後掛三句別人的台詞。
  兩種簡寫可以用:群像格寫 "all four cats" 就代表四貓都在(小次郎要另外點名);
  **有人在畫外說話,就寫 "SAMURAI CAT speaks from off-panel"——一樣要點名**,
  這樣生圖端才知道那句話不屬於畫面裡的任何一隻
- **這是異世界,不是機房。** 每一話至少要有一樣**只有異世界才有**的東西真的出現
  在畫面上:怪物、魔法戰鬥、地形、村民 NPC、非現實的道具。工程師的哏是這部的
  笑點來源,但它只能當**比喻**——魔力是配給的、黑塔會例行維護——不可以整話
  的舞台就是一個機房、四隻貓圍著螢幕打字。落差要成立,異世界那一邊得真的存在。
  最近幾話已經連續五話都在辦公室裡,這一話要把場景拉回異世界。
  **`fantasy` 欄位要填你這一話真的會畫出來的那樣東西**(例:a moss-covered stone
  golem guarding a ravine),而且它要在至少兩頁的 `scene` 裡真的出現。填螢幕、
  主機房、全像投影、程式碼一律不算,那些是辦公室搬過來的
- **`scene` 裡的動作要用手做**。這五隻是擬人化的貓，站著、有手、會拿東西——
  拔插頭就用手拔，不要寫「用貓牙咬住電纜扯出來」「用後腿把電纜踢回插座」。
  第三話第 04 頁就是這樣出事的：模型很聽話地照畫，姿勢卡在中間，人看一眼
  就知道不對。真要用嘴或用腳，得是刻意的笑點，而且要跟角色個性對得上
  （小鳥不啾是冷靜吐槽型，不會又咬又踢）{retry_block}"""


def _strip_fence(s):
    """LLM 常常還是會包 markdown 圍籬,拆掉。"""
    m = re.search(r'```(?:json)?\s*(.+?)\s*```', s, re.S)
    return m.group(1) if m else s.strip()


def call_llm(text):
    """取得企劃文字。看 PLANNER_PROVIDER 決定打誰。"""
    if PLANNER_PROVIDER == 'openai':
        return _llm_openai(text)
    if PLANNER_PROVIDER != 'gemini':
        raise RuntimeError(f'不認得的 PLANNER_PROVIDER:{PLANNER_PROVIDER}(只有 gemini / openai)')
    return _llm_gemini(text)


def _llm_openai(text):
    """打任何 OpenAI 相容的 chat completions 端點。

    Groq、Ollama、OpenRouter 都是同一個形狀,差別只在 OPENAI_BASE_URL 與模型名。
    `response_format` 要 json_object,少了它模型很愛包一層 markdown 圍籬——
    _strip_fence 擋得掉,但能不用擋就不要擋。
    """
    key = os.environ.get('OPENAI_API_KEY', '')
    if not key:
        raise RuntimeError('沒有 OPENAI_API_KEY,無法呼叫 OpenAI 相容端點')
    # 上限一定要設,而且要設大。實測(2026-08-01,同一份 prompt):
    #   Groq openai/gpt-oss-120b 不設 → finish_reason=length,3072 就被切斷;
    #                            設了 → 3865 token 完成
    #   llmshare glm-5.2(推理模型)→ 11179 token 才完成,16384 全部燒光還沒寫完
    # 推理模型的 reasoning_content 也吃這份額度,所以「一份企劃才 4000 token」
    # 這個直覺會害人。上限只是上限,計費看實際產出,往大裡設沒有壞處。
    body = json.dumps({
        'model': OPENAI_MODEL,
        'messages': [{'role': 'user', 'content': text}],
        'response_format': {'type': 'json_object'},
        'max_tokens': OPENAI_MAX_TOKENS,
    }).encode()
    req = urllib.request.Request(
        f'{OPENAI_BASE}/chat/completions', body,
        {'Content-Type': 'application/json', 'Authorization': f'Bearer {key}',
         'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=300) as f:
        payload = json.load(f)
    choices = (payload.get('choices') if isinstance(payload, dict) else None) or []
    choice = choices[0] if choices else {}
    content = (choice.get('message') or {}).get('content')

    # 被 max_tokens 切斷時 content 是一段半截的 JSON,直接回去會在 json.loads
    # 那裡丟「Expecting value」,跟真正的原因差很遠。這裡先認出來,錯誤訊息
    # 直接講要調哪個環境變數。
    if choice.get('finish_reason') == 'length':
        raise RuntimeError(
            f'{OPENAI_MODEL} 的輸出被切斷(finish_reason=length,目前 '
            f'OPENAI_MAX_TOKENS={OPENAI_MAX_TOKENS})。調大再跑一次;推理模型的'
            '思考過程也吃這份額度,實測 glm-5.2 要 11000 以上才寫得完一份企劃。')
    if content:
        return content
    # 裸 KeyError 看不出是被擋、額度用完、還是模型名打錯,把診斷資訊帶出來。
    raise RuntimeError(
        f'{OPENAI_MODEL} 回應裡沒有可用的文字內容'
        '(取不到 choices[0].message.content)。'
        f' finish_reason={choice.get("finish_reason")!r}'
        f' payload 前 300 字:{json.dumps(payload, ensure_ascii=False)[:300]}')


def _llm_gemini(text):
    """打 Gemini 形狀的端點(我的自架中繼,或官方 generativelanguage)。"""
    key = os.environ.get('GEMINI_API_KEY', '')
    if not key:
        raise RuntimeError('沒有 GEMINI_API_KEY,無法呼叫 gemini-web')
    url = f'{GEMINI_BASE}/v1beta/models/{GEMINI_MODEL}:generateContent?key={key}'
    body = json.dumps({
        'contents': [{'parts': [{'text': text}]}],
        'generationConfig': {'response_mime_type': 'application/json'},
    }).encode()
    req = urllib.request.Request(url, body,
                                 {'Content-Type': 'application/json', 'User-Agent': UA})
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
            f'{GEMINI_MODEL} 回應裡沒有可用的文字內容'
            '(取不到 candidates[0].content.parts[0].text)。'
            f' finishReason={finish_reason!r} promptFeedback={prompt_feedback!r}'
            f' payload 前 300 字:{json.dumps(payload, ensure_ascii=False)[:300]}') from None


def make_plan(canon, wishes, previous_errors=None):
    text = call_llm(build_planner_prompt(canon, wishes, previous_errors))
    try:
        return json.loads(_strip_fence(text))
    except json.JSONDecodeError as e:
        # 拿掉包裝直接讓 JSONDecodeError 往外丟,追蹤只看得到「哪個字元解析
        # 失敗」,看不到 LLM 實際回了什麼——這裡把原文前 300 字帶出來,才
        # 查得出是圍籬沒拆乾淨還是 LLM 真的沒照格式回。
        raise RuntimeError(
            f'LLM 回傳的不是合法 JSON:{e}。實際回傳內容前 300 字:{text[:300]}') from None


IMG_BASE = os.environ.get('CODEX_IMAGE_BASE_URL') or 'https://ching-tech.ddns.net/codex-image'

# 出圖走哪個後端。預設 codex(我自架的 codex-image-service);fork 的人設成
# gemini 就改打 Google 官方的影像模型,只要一把 AI Studio 金鑰,不必自架東西。
# 沒有 gemini-web 這個選項:它的 /api/edit 只吃一張參考圖,而這條產線一頁
# 最多要傳 8 張(畫風錨 + 道具/場景 + 每個出場角色),塞不進去。
IMAGE_PROVIDER = (os.environ.get('IMAGE_PROVIDER') or 'codex').lower()
GEMINI_IMAGE_BASE = os.environ.get('GEMINI_IMAGE_BASE_URL') or 'https://generativelanguage.googleapis.com'
GEMINI_IMAGE_MODEL = os.environ.get('GEMINI_IMAGE_MODEL') or 'gemini-3.1-flash-image-preview'
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


def pr_body(plan, n, wishes, wish_err=None, branch=None, verdicts=None):
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
    if verdicts:
        bad = [v for v in verdicts if v[1] != 'PASS']
        out.append('\n## 機器驗收\n')
        if bad:
            out.append('**這幾頁沒過,先看它們**（規則在 `story/verify.md`）：\n')
            out += [f'- 第 {name} 頁 `{verdict}`：{detail or "（沒給理由）"}'
                    for name, verdict, detail in bad]
            out.append('\n它也會判錯——抓不到「角色被畫得像另一個角色但仍分辨得出來」那類，'
                       '偶爾會把讀不清楚的字判成錯字。**它說沒過不代表一定要重生，'
                       '它說過了也不代表你不用看。**\n')
        else:
            out.append(f'{len(verdicts)} 頁全過。這只代表沒踩到寫死的那幾條規則'
                       '（眼鏡戴錯人、對白錯字、狀聲字頁碼），'
                       '**不代表圖畫對了**——底下還是要逐頁看。\n')

    out.append('\n## 逐頁對照\n')
    out.append('**你要看的不是劇情，是圖有沒有照劇本畫。** '
               '劇情在文字層通常沒問題，會出事的是「劇本寫的」跟「圖畫出來的」之間那道縫——'
               '第二話里歐的「隱形只隱一半」就是分鏡完全正確、圖卻畫成一隻完整的橘貓，'
               '整頁的笑點沒了，而讀分鏡檔案完全看不出來。\n')
    cover = ROOT / f'images/ep{n}/00-cover.webp'
    if cover.is_file():
        # 封面本來完全沒出現在 PR 裡,而它跟內頁一樣是生成的、一樣會出錯。
        out.append('\n### 封面\n')
        out.append(f'![封面](https://raw.githubusercontent.com/yazelin/neko-tensei/'
                   f'{branch}/images/ep{n}/00-cover.webp)\n')
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
PAGE_W = 1024        # 站上每一頁的寬度,ep/*.html 的 <img> 寫死這個數字


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
    im = Image.open(io.BytesIO(raw)).convert('RGB')
    # 站上的 <img> 寫死 width=1024 height=1536,比這更大的圖只是讓 PWA 的
    # precache 變重。Gemini 那條要 2K(1696×2528)是為了對白銳利,縮回來
    # 才落檔;codex 那條本來就是 1024,這裡是 no-op。
    if im.width > PAGE_W:
        im = im.resize((PAGE_W, round(im.height * PAGE_W / im.width)), Image.LANCZOS)
    im.save(out, 'WEBP', quality=WEBP_QUALITY)


def generate_image(name, keys, body, out):
    """出一張圖存到 out。看 IMAGE_PROVIDER 決定打誰。"""
    if IMAGE_PROVIDER == 'gemini':
        return _img_gemini(name, keys, body, out)
    if IMAGE_PROVIDER != 'codex':
        raise RuntimeError(f'不認得的 IMAGE_PROVIDER:{IMAGE_PROVIDER}(只有 codex / gemini)')
    return _img_codex(name, keys, body, out)


def _img_gemini(name, keys, body, out):
    """打 Gemini 的影像模型。同步回圖,沒有 job 可以輪詢。

    參考圖用 inline_data 一張一張塞進同一個 parts 陣列,順序跟 codex 那條
    一樣(image 1 是畫風錨,後面才是道具與角色),因為 prompt 裡的
    `REFERENCE IMAGES:` 是照順序指名的,順序錯了模型就對不上是誰。
    """
    key = os.environ.get('GEMINI_IMAGE_KEY') or os.environ.get('GEMINI_API_KEY', '')
    if not key:
        raise RuntimeError('沒有 GEMINI_IMAGE_KEY(或 GEMINI_API_KEY),無法出圖')
    parts = [{'text': prompt.build_prompt(name, keys, body)}]
    for k in keys:
        p = ROOT / prompt.REF[k][0]
        parts.append({'inline_data': {
            'mime_type': mimetypes.guess_type(p.name)[0] or 'image/webp',
            'data': base64.b64encode(p.read_bytes()).decode()}})
    url = (f'{GEMINI_IMAGE_BASE}/v1beta/models/{GEMINI_IMAGE_MODEL}'
           f':generateContent?key={key}')
    # imageConfig 一定要給。實測(2026-08-01,gemini-3.1-flash-image-preview):
    # 什麼都不給 → 回 1408×768 的橫幅,一頁三格的直式分鏡直接毀掉;
    # aspectRatio=2:3 → 848×1264;再加 imageSize=2K → 1696×2528。
    # prompt 裡雖然寫了 portrait 2:3,但那只是「有時候會聽」,不能當設定用。
    # 要 2K 是為了對白清楚:落檔時再縮到站上的 1024 寬,縮圖比直接生小圖銳利。
    body = {'contents': [{'parts': parts}],
            'generationConfig': {'imageConfig': {'aspectRatio': '2:3', 'imageSize': '2K'}}}
    req = urllib.request.Request(url, json.dumps(body).encode(),
                                 {'Content-Type': 'application/json', 'User-Agent': UA})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=600) as f:
        payload = json.load(f)
    raw = _gemini_image_bytes(payload)
    out.parent.mkdir(parents=True, exist_ok=True)
    save_image(raw, out)
    print(f'  -> {name} ok {int(time.time() - t0)}s '
          f'{out.stat().st_size / 1e6:.2f}MB', flush=True)


def _gemini_image_bytes(payload):
    """從回應裡挑出第一張圖的位元組。純函式,好測。

    回應是 parts 陣列,文字與圖混在一起(模型常常先講一句「Here is…」),
    所以要逐個找 inlineData,不能寫死 parts[0]。找不到就把 finishReason
    帶出來——被安全機制擋掉時 parts 整個不存在,跟「模型只回了文字」是
    兩種完全不同的狀況,錯誤訊息要分得出來。
    """
    cands = (payload.get('candidates') if isinstance(payload, dict) else None) or []
    for part in ((cands[0].get('content') or {}).get('parts') or []) if cands else []:
        data = (part.get('inlineData') or part.get('inline_data') or {}).get('data')
        if data:
            return base64.b64decode(data)
    raise RuntimeError(
        '出圖失敗:回應裡沒有任何 inlineData。'
        f' finishReason={(cands[0].get("finishReason") if cands else None)!r}'
        f' payload 前 300 字:{json.dumps(payload, ensure_ascii=False)[:300]}')


def _img_codex(name, keys, body, out):
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
    hdr = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json',
           'User-Agent': UA}
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
                                   headers={'Authorization': hdr['Authorization'],
                                            'User-Agent': UA})
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


WORDING_PROMPT = """你是繁體中文校對。下面是一部漫畫的對白清單,每行前面是編號。

找出**不成詞的錯字**:每個字單獨看都是合法的正體中文字,但湊在一起不成詞,
通常是同音或形近誤用。已經發生過的例子:「完蛋」寫成「完旦」、刷卡的
「嗶」寫成「逼」。

只挑真的不成詞的。這是一部搞笑奇幻漫畫,角色是工程師,以下都**不算錯**:
- 網路用語、故意的諧音梗、自創詞
- 中英夾雜(Bug、Token、Log、Patch 這類)
- 語氣詞與拉長音(「欸——」「唔…」)
- 專有名詞與角色暱稱(小鳥不啾、小白++、中年攻城屍、里歐、荒坂小次郎)

用 JSON 回答,格式:{"problems": [{"line": 編號, "wrong": "錯詞", "right": "正確的詞"}]}
沒有問題就回 {"problems": []}。不要解釋,只回 JSON。

對白清單:
%s"""


def wording_problems(plan):
    """用 LLM 校對對白裡的錯字。回問題清單,空清單代表沒問題。

    **這是 validate_plan 抓不到的那一類。** validate_plan 管頁數、框型、簡繁、
    角色、道具 id,那些都有明確規則可以寫成程式;但「完旦」是合法字元組成的
    錯詞,要抓它得有詞庫,而這個 repo 的紅線是不手維護字表(當初手打的簡體表
    混進「那」「只」「反」,差點全擋)。用 LLM 判詞就不需要字表。

    放在企劃階段是刻意的:這裡是純文字,一次幾秒、不花出圖額度,抓到就重出
    企劃,錯字根本不會被畫到圖上。等圖出來再讀字又貴又會誤讀——實測會把
    「還敢慶祝」讀成「還敢慶視」。出圖後那道檢查(story/verify.md)保留當
    第二道網,不是取代這道。

    校對本身失敗(模型掛了、回了不是 JSON)一律當作沒問題,只印一行警告:
    這是加分項,不該讓整條線停在校對器上。
    """
    lines = [(i, text) for i, (_, _, _, text) in enumerate(_lines(plan), 1) if text]
    if not lines:
        return []
    listing = '\n'.join(f'{i}. {text}' for i, text in lines)
    try:
        raw = call_llm(WORDING_PROMPT % listing)
        problems = json.loads(_strip_fence(raw)).get('problems') or []
    except Exception as e:
        print(f'  對白校對跳過(校對器自己出錯): {str(e)[:160]}', flush=True)
        return []

    by_line = dict(lines)
    errs = []
    for p in problems:
        if not isinstance(p, dict):
            continue
        wrong = str(p.get('wrong') or '').strip()
        # 模型偶爾會回一個原文裡根本沒有的詞。對不上就丟掉,不要拿幻覺去
        # 擋掉一份好企劃。
        text = by_line.get(p.get('line'))
        if not wrong or not text or wrong not in text:
            continue
        right = str(p.get('right') or '').strip()
        errs.append(f'第 {p.get("line")} 句「{text}」的「{wrong}」疑似錯字'
                    + (f',應為「{right}」' if right else ''))
    return errs


PLAN_ATTEMPTS = 3


def name_offpanel_speakers(plan):
    """把沒被畫面描述點名的說話者,補成「在畫外說話」。回補過的清單。

    模型在這條規則上就是收斂不了:回饋錯誤清單之後從 17 處降到 1 到 3 處,
    再重試也還是在那個區間跳。與其擲骰子,不如直接修——而且**補成畫外音正好
    是最保守的解讀**:明說那句話不屬於畫面裡的任何一隻,生圖端就不會自己補一隻
    上去,那正是原本那個 bug(第六話六頁裡四頁的「老夫」都被畫給了小鳥不啾)。

    代價是那一格少一個角色出鏡。但「少一隻」比「多一隻長得像別人的」好得多,
    而且人在 PR 上看得到分鏡檔寫著 speaks from off-panel。
    """
    repaired = []
    for pg in plan.get('pages') or []:
        for panel in pg.get('panels') or []:
            scene = panel.get('scene') or ''
            upper = scene.upper()
            grouped = any(g in upper for g in GROUP_PHRASES)
            for sp in dict.fromkeys(ln.get('speaker') for ln in (panel.get('lines') or [])):
                if sp not in CHAR_TAGS:
                    continue
                tag = CHAR_TAGS[sp]
                if tag in scene or sp.upper() in upper or (grouped and sp in FOUR_CATS):
                    continue
                scene = f'{scene.rstrip()} {tag} speaks from off-panel.'
                upper = scene.upper()
                repaired.append(f'第 {pg.get("n")} 頁:{tag} 沒被畫面描述點名,補成畫外音')
            panel['scene'] = scene
    return repaired

def plan_with_retry(canon, wishes, titles, n):
    """企劃不過就重試,連 PLAN_ATTEMPTS 次都不過才放棄。

    **重試時把上一次的錯誤清單附在 prompt 後面。** 原本是同一份 prompt 再擲一
    次,理由是「機率性輸出,第一次不過通常不是 prompt 寫壞」——那對零星失誤
    成立,但對系統性的錯不成立。「每格要點名說話者」這條上線那天,模型連兩次
    都在同樣的地方漏,違規數 17 → 6 → 4,方向對但收斂不了;把「你上一版這幾格
    漏了誰」直接告訴它,比期待它自己開竅有效得多。

    只回饋錯誤、不改規則本身:規則放寬會把問題退回生圖端,那才是貴的地方。
    """
    errs = []
    for attempt in range(1, PLAN_ATTEMPTS + 1):
        plan = make_plan(canon, wishes, previous_errors=errs)
        for line in name_offpanel_speakers(plan):
            print(' 自動修補:', line)
        # 校對排在規則驗證之後:規則不過就沒必要再花一次 LLM 呼叫去校對一份
        # 本來就要重擲的企劃。
        errs = validate_plan(plan, n, titles) or wording_problems(plan)
        if not errs:
            return plan
        print(f'企劃第 {attempt}/{PLAN_ATTEMPTS} 次沒過:')
        for e in errs:
            print(' -', e)
    raise RuntimeError(f'企劃連 {PLAN_ATTEMPTS} 次都沒過驗證:' + '；'.join(errs))


TW = zoneinfo.ZoneInfo('Asia/Taipei')


def today_tw():
    """台灣的今天。**不要用 datetime.date.today()**。

    這條線跑在 GitHub runner 上,系統時區是 UTC。第四話的落檔跑在
    2026-07-31T17:12Z,台灣時間已經是 8/1 凌晨,但 date.today() 給的是 7/31——
    這個日期會印在首頁的話數列表,也會進 sitemap 的 lastmod。讀者在台灣,
    日期就該是台灣的。

    zoneinfo 是標準函式庫,不算新增相依。
    """
    return datetime.datetime.now(TW).date().isoformat()


def verify_episode(n, plan):
    """出圖後逐頁跑視覺驗收。回 [(頁名, 判定, 說明)],空清單代表沒跑。

    這是 validate_plan 與對白校對之後的第三道:前兩道都在文字層,看不到「劇本
    寫的」跟「圖畫出來的」之間那道縫——第二話里歐的「隱形只隱一半」分鏡完全
    正確,圖卻畫成一隻完整的橘貓,讀分鏡檔案永遠看不出來。

    規則與抓得到什麼在 story/verify.md。**不擋落檔**:判定寫進 PR 內文給人看,
    人才是閘門。機器判錯而擋掉整話,比漏報一頁還糟——重跑一話是 36 分鐘。
    """
    key = os.environ.get('CODEX_IMAGE_KEY')
    if not key:
        print('沒有 CODEX_IMAGE_KEY,跳過視覺驗收')
        return []
    sys.path.insert(0, str(ROOT / 'scripts'))
    try:
        import verify_pages
        rules = verify_pages.load_rules()
        check = verify_pages.check_page_service
    except Exception as e:
        print(f'視覺驗收跳過(載不進來): {str(e)[:160]}', flush=True)
        return []

    out = []
    # 封面也要驗。它跟內頁走同一套角色設定,一樣會把眼鏡戴到別人臉上;第六話
    # 就是因為這裡只跑 plan['pages'],封面完全沒被看過。沒有對白所以不傳劇本,
    # 規則 B 會自己跳過。
    pages = [('00-cover', '')] + [(pg['n'], page_body(pg)) for pg in plan['pages']]
    for name, context in pages:
        img = ROOT / f'images/ep{n}' / f"{name}.webp"
        if not img.is_file():
            continue
        try:
            # 把這一頁的劇本一起送過去。說話者被畫成另一個角色是這條產線最常
            # 見的錯,而圖本身看起來完全正常——沒有劇本可以對照,那一類永遠
            # 抓不到(第六話第 02、03 頁就是這樣漏掉的)。
            verdict, secs, text = check(img, rules, context)
        except Exception as e:
            # 驗收器自己壞掉要說出來,不能靜靜地當成這一話沒問題。
            out.append((name, 'ERR', f'驗收沒跑成功:{str(e)[:160]}'))
            print(f'  {name} 驗收失敗: {str(e)[:160]}', flush=True)
            continue
        detail = ' / '.join(l.strip() for l in text.splitlines() if '違規' in l)
        out.append((name, verdict, detail))
        print(f'  {name} {verdict} {secs:.0f}s {detail}', flush=True)
    return out

def publish(plan, n, has_cover):
    """落檔:圖已經在 images/epN/ 了,這裡處理分鏡、episodes.json 與 build。"""
    (ROOT / 'story' / f'ep{n}.md').write_text(render_storyboard(plan, n), 'utf-8')

    cfg_path = ROOT / 'episodes.json'
    cfg = json.loads(cfg_path.read_text('utf-8'))
    date = today_tw()
    cfg['episodes'].append(episode_entry(plan, n, date, has_cover))
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + '\n', 'utf-8')

    # sw.js 的兩個版號不用在這裡動:build.py 會從殼檔與圖檔的內容重算,
    # 多了一頁 epN.html、多了七張圖,兩個 hash 自然都會變。
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

    verdicts = verify_episode(n, plan) if not a.skip_images else []

    publish(plan, n, has_cover)
    (ROOT / f'.pr-body-ep{n}.md').write_text(
        pr_body(plan, n, wishes, wish_err, verdicts=verdicts), 'utf-8')
    clear_cached_plan(n)          # 落檔成功,這一話的續傳狀態不再需要
    print('落檔完成。PR 內文在 .pr-body-ep%d.md' % n)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
