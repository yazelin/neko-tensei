#!/usr/bin/env python3
"""從 episodes.json 產生每一話的閱讀頁,並同步首頁話數列表、sitemap、sw.js 快取清單。

單一事實來源 = episodes.json。加新話只要:
  1. 圖放進 images/epN/
  2. episodes.json 加一段
  3. python3 build.py
角色頁(char-*.html)與首頁的文案是手寫的,本腳本只碰標記之間的區塊。
"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).parent
CFG = json.loads((ROOT / 'episodes.json').read_text('utf-8'))
BASE = CFG['site']['base']
SITE = CFG['site']['title']
EPS = CFG['episodes']
FOOTER = (ROOT / 'partials' / 'footer.html').read_text('utf-8')

HEAD = """<!doctype html><html lang="zh-Hant-TW"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{h1}｜{site}</title>
<meta name="description" content="{desc} {series}，{h1}完整閱讀。">
<link rel="canonical" href="{url}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="{site}">
<meta property="og:locale" content="zh_TW">
<meta property="og:title" content="{h1}｜{site}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{base}og.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{h1}｜{site}">
<meta name="twitter:description" content="{desc}">
<meta name="twitter:image" content="{base}og.jpg">
<link rel="manifest" href="manifest.json">
<meta name="theme-color" content="#12141d">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="貓貓轉生">
<link rel="icon" type="image/png" sizes="32x32" href="favicon-32.png">
<link rel="icon" type="image/png" sizes="192x192" href="icon-192.png">
<link rel="apple-touch-icon" href="icon-180.png">
<link rel="stylesheet" href="style.css">
<script type="application/ld+json">
{{"@context":"https://schema.org","@type":"ComicIssue","issueNumber":{n},
"name":"{h1}","inLanguage":"zh-Hant-TW",
"author":{{"@type":"Person","name":"林亞澤"}},
"isPartOf":{{"@type":"ComicSeries","name":"{site}","url":"{base}"}},
"url":"{url}",
"image":"{base}og.jpg"}}
</script>
</head><body>

<div class="wrap">
  <nav class="top">
    <img src="icon-192.png" alt="" width="34" height="34">
    <a class="site" href="./">{site}</a>
    <span class="sp"></span>
    <a href="./#characters">角色</a>
  </nav>
</div>

<main class="reader">
  <h1 style="position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)">{h1}</h1>
"""

CN = '一二三四五六七八九十'


def zh(n):
    return CN[n - 1] if 1 <= n <= 10 else str(n)


def build_episode(ep, prev, nxt):
    h1 = f"第{zh(ep['n'])}話：{ep['title']}"
    url = f"{BASE}ep{ep['n']}.html"
    out = [HEAD.format(h1=h1, site=SITE, desc=ep['desc'], series=SITE,
                       url=url, base=BASE, n=ep['n'])]
    for i, p in enumerate(ep['pages']):
        extra = ' fetchpriority="high"' if i == 0 else ' loading="lazy"'
        out.append(f'  <img src="images/ep{ep["n"]}/{p["f"]}" width="1024" height="1536"{extra}\n'
                   f'       alt="{p["alt"]}">\n')
    out.append('  <p class="credit">%s</p>\n' % ep['credit'])
    out.append('  <nav class="reader-nav">\n    <a class="btn ghost" href="./">回首頁</a>\n')
    if prev:
        out.append(f'    <a class="btn ghost" href="ep{prev["n"]}.html">上一話</a>\n')
    if nxt:
        out.append(f'    <a class="btn" href="ep{nxt["n"]}.html">下一話：{nxt["title"]}</a>\n')
    else:
        out.append(f'    <span class="btn ghost" aria-disabled="true" style="opacity:.45">'
                   f'第{zh(ep["n"] + 1)}話 未完待續……</span>\n')
    out.append('  </nav>\n</main>\n\n')
    out.append(FOOTER)
    (ROOT / f'ep{ep["n"]}.html').write_text(''.join(out), 'utf-8')


def splice(path, key, body):
    """把 body 換進 <!--key:start--> … <!--key:end--> 之間。"""
    f = ROOT / path
    t = f.read_text('utf-8')
    pat = re.compile(rf'((?:<!--|/\* ){key}:start(?:-->|\ \*/)\n).*?'
                     rf'(\s*(?:<!--|/\* ){key}:end(?:-->|\ \*/))', re.S)
    if not pat.search(t):
        sys.exit(f'{path} 找不到 {key} 標記')
    f.write_text(pat.sub(lambda m: m.group(1) + body + m.group(2), t), 'utf-8')


def main():
    for i, ep in enumerate(EPS):
        build_episode(ep, EPS[i - 1] if i else None, EPS[i + 1] if i + 1 < len(EPS) else None)

    # 首頁話數列表(最新的排上面)
    rows = []
    for ep in reversed(EPS):
        rows.append(f'      <li><a href="ep{ep["n"]}.html"><span class="no">第{zh(ep["n"])}話</span>'
                    f'<span>{ep["title"]}</span><small>{ep["date"]}</small></a></li>')
    rows.append(f'      <li><div class="soon"><span class="no">第{zh(EPS[-1]["n"] + 1)}話</span>'
                f'<span>那座黑塔上的魔法陣，又是誰點亮的？</span></div></li>')
    splice('index.html', 'episodes', '\n'.join(rows))

    # 首頁最新一話的封面連結
    last = EPS[-1]
    splice('index.html', 'latest',
           f'      <a class="cover" href="ep{last["n"]}.html" aria-label="開始閱讀第{zh(last["n"])}話">\n'
           f'        <img src="images/ep{last["n"]}/{last["pages"][0]["f"]}" width="1024" height="1536"\n'
           f'             alt="{last["pages"][0]["alt"]}" fetchpriority="high">\n'
           f'      </a>\n'
           f'      <div>\n'
           f'        <a class="btn" href="ep{last["n"]}.html">閱讀 第{zh(last["n"])}話</a>\n'
           f'        <button class="btn ghost" id="inst" type="button">安裝到手機</button>\n'
           f'      </div>')

    # sitemap
    urls = [f'  <url><loc>{BASE}</loc><lastmod>{EPS[-1]["date"]}</lastmod></url>']
    for ep in EPS:
        urls.append(f'  <url><loc>{BASE}ep{ep["n"]}.html</loc><lastmod>{ep["date"]}</lastmod></url>')
    for c in CFG['characters']:
        urls.append(f'  <url><loc>{BASE}char-{c["slug"]}.html</loc>'
                    f'<lastmod>{EPS[-1]["date"]}</lastmod></url>')
    (ROOT / 'sitemap.xml').write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + '\n'.join(urls) + '\n</urlset>\n', 'utf-8')

    # sw.js:殼與暖快取清單
    shell = ["  './', './index.html',"]
    shell.append('  ' + ' '.join(f"'./ep{e['n']}.html'," for e in EPS))
    shell.append('  ' + ' '.join(f"'./char-{c['slug']}.html'," for c in CFG['characters']))
    shell.append("  './style.css', './manifest.json',")
    shell.append("  './icon-192.png', './icon-180.png', './favicon-32.png'")
    splice('sw.js', 'shell', '\n'.join(shell))

    warm = []
    for ep in reversed(EPS):          # 最新一話先暖:讀者最可能開它
        for p in ep['pages']:
            warm.append(f"./images/ep{ep['n']}/{p['f']}")
    warm += [f"./images/char-{c['slug']}.webp" for c in CFG['characters']]
    warm += ['./icon-512.png', './og.jpg']
    lines, cur = [], '  '
    for u in warm:
        item = f"'{u}', "
        if len(cur) + len(item) > 96:
            lines.append(cur.rstrip()); cur = '  '
        cur += item
    lines.append(cur.rstrip().rstrip(','))
    splice('sw.js', 'warm', '\n'.join(lines))

    print(f'built {len(EPS)} episodes, {len(CFG["characters"])} characters')


if __name__ == '__main__':
    main()
