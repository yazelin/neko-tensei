#!/usr/bin/env python3
"""自動產出下一話:讀 canon 與許願 → LLM 出企劃 → 驗企劃 → 出圖 → 落檔。

設計在 docs/superpowers/specs/2026-07-31-auto-episode-pipeline-design.md。
唯一的 pip 相依是 `opencc-python-reimplemented`(驗簡繁用),其餘一律標準
函式庫——build.py 仍是純 stdlib,這裡是整條 pipeline 例外的那一個套件。

跑法:
  python3 scripts/next_episode.py --dry-run          只出企劃並驗證,不出圖不落檔
  python3 scripts/next_episode.py --plan-from p.json 跳過 LLM,用現成企劃
  python3 scripts/next_episode.py                    整條跑完
"""
import json
import pathlib
import subprocess
import sys

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
