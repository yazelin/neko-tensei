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
