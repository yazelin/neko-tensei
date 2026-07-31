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
    """
    if not text:
        return None
    m = _simplified_map()
    for ch in text:
        cands = m.get(ch)
        if cands and ch not in cands:
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
