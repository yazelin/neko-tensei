#!/usr/bin/env python3
"""從 episodes.json 產生每一話的閱讀頁,並同步首頁話數列表、sitemap、sw.js 快取清單。

單一事實來源 = episodes.json。加新話只要:
  1. 圖放進 images/epN/
  2. episodes.json 加一段
  3. python3 build.py
角色頁(char-*.html)與首頁的文案是手寫的,本腳本只碰標記之間的區塊。
"""
import hashlib, html, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).parent
CFG = json.loads((ROOT / 'episodes.json').read_text('utf-8'))
BASE = CFG['site']['base']
SITE = CFG['site']['title']
EPS = CFG['episodes']
FOOTER = (ROOT / 'partials' / 'footer.html').read_text('utf-8')

# GitHub Discussions 的分類 id。用 id 不用名稱——之後在 GitHub 上把分類
# 改成中文名也不會壞,giscus 實際比對的是 id。
GENERAL_CAT = 'DIC_kwDOToGp784DCVjJ'   # 內建 General,每話一串

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
<meta property="og:image" content="{base}assets/og.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{h1}｜{site}">
<meta name="twitter:description" content="{desc}">
<meta name="twitter:image" content="{base}assets/og.jpg">
<link rel="manifest" href="../manifest.json">
<meta name="theme-color" content="#12141d">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="貓貓轉生">
<link rel="icon" type="image/png" sizes="32x32" href="../assets/favicon-32.png">
<link rel="icon" type="image/png" sizes="192x192" href="../assets/icon-192.png">
<link rel="apple-touch-icon" href="../assets/icon-180.png">
<link rel="stylesheet" href="../style.css">
<script src="../app.js" defer></script>
<script type="application/ld+json">
{{"@context":"https://schema.org","@type":"ComicIssue","issueNumber":{n},
"name":"{h1}","inLanguage":"zh-Hant-TW",
"author":{{"@type":"Person","name":"林亞澤"}},
"isPartOf":{{"@type":"ComicSeries","name":"{site}","url":"{base}"}},
"url":"{url}",
"image":"{base}assets/og.jpg"}}
</script>
</head><body data-ep="{n}">

<nav class="reader-top">
  <a class="back" href="../" aria-label="回首頁">‹</a>
  <span class="ttl">{h1}</span>
  <a class="chars" href="../#characters" aria-label="角色"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm0 2c-4 0-8 2-8 5v1h16v-1c0-3-4-5-8-5z"/></svg></a>
  <a class="eps" href="../#episodes" aria-label="話數">☰</a>
</nav>

<main class="reader">
  <h1 style="position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)">{h1}</h1>
"""

# 快取版號的逃生口。平常不要動——版號由檔案內容算出來,改殼檔或換圖會自己變。
# 只有 hash 看不到的情況才 +1:改了 sw.js 自己的快取策略、或舊快取裡已經有髒
# 資料要強制所有讀者重來。sw.js 不能把自己算進 hash(會自我參照)。
EPOCH = 'v20'


def digest(paths):
    """一組檔案的內容指紋。路徑也算進去,所以清單增刪同樣會讓版號變。

    只涵蓋 SHELL_FILES 與 WARM 這兩份清單裡的檔案。**別把大檔放進 SHELL_FILES**
    ——殼是「任何一個 byte 變動就整包換名重抓」的那一層,現在只有幾百 KB,
    塞進一張圖就會變成「改一行 CSS,讀者重抓好幾 MB」。
    """
    h = hashlib.sha256()
    for p in sorted(paths):
        h.update(p.encode())
        h.update(hashlib.sha256((ROOT / p).read_bytes()).digest())
    return h.hexdigest()[:8]


CN = '一二三四五六七八九十'


def zh(n):
    return CN[n - 1] if 1 <= n <= 10 else str(n)


def build_episode(ep, prev, nxt):
    h1 = f"第{zh(ep['n'])}話：{ep['title']}"
    url = f"{BASE}ep/{ep["n"]}.html"
    out = [HEAD.format(h1=h1, site=SITE, desc=ep['desc'], series=SITE,
                       url=url, base=BASE, n=ep['n'])]
    for i, p in enumerate(ep['pages']):
        extra = ' fetchpriority="high"' if i == 0 else ' loading="lazy"'
        out.append(f'  <img id="p{i}" src="../images/ep{ep["n"]}/{p["f"]}"\n'
                   f'       width="1024" height="1536"{extra}\n'
                   f'       alt="{html.escape(p["alt"], quote=True)}">\n')
    out.append('  <p class="credit">%s</p>\n' % ep['credit'])
    out.append('  <nav class="reader-nav">\n    <a class="btn ghost" href="../">回首頁</a>\n')
    if prev:
        out.append(f'    <a class="btn ghost" href="{prev["n"]}.html">上一話</a>\n')
    if nxt:
        out.append(f'    <a class="btn" href="{nxt["n"]}.html">下一話：{nxt["title"]}</a>\n')
    else:
        out.append(f'    <span class="btn ghost" aria-disabled="true" style="opacity:.45">'
                   f'第{zh(ep["n"] + 1)}話 未完待續……</span>\n')
    out.append('  </nav>\n</main>\n\n')
    out.append('<section class="wrap talk">\n  <h2>這一話的討論</h2>\n'
               f'  <div id="giscus" data-category-id="{GENERAL_CAT}" data-mapping="pathname"></div>\n'
               '</section>\n\n')
    out.append(f'<div class="progress" aria-hidden="true"><i></i>'
               f'<span>1/{len(ep["pages"])}</span></div>\n\n')
    out.append(FOOTER)
    (ROOT / 'ep' / f'{ep["n"]}.html').write_text(''.join(out), 'utf-8')


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
        rows.append(f'      <li><a href="ep/{ep["n"]}.html"><span class="no">第{zh(ep["n"])}話</span>'
                    f'<span>{ep["title"]}</span><small>{ep["date"]}</small></a></li>')
    rows.append(f'      <li><div class="soon"><span class="no">第{zh(EPS[-1]["n"] + 1)}話</span>'
                f'<span>那座黑塔上的魔法陣，又是誰點亮的？</span></div></li>')
    splice('index.html', 'episodes', '\n'.join(rows))

    # 首頁大圖固定放第一話——這是連載,新讀者的門口是第一話,不是最新一話。
    # 最新一話當輔助入口放在按鈕列,避免大圖直接劇透後面的劇情。
    first, last = EPS[0], EPS[-1]
    hero = (f'      <a class="cover" href="ep/{first["n"]}.html" aria-label="開始閱讀第{zh(first["n"])}話">\n'
            f'        <img src="images/ep{first["n"]}/{first["pages"][0]["f"]}" width="1024" height="1536"\n'
            f'             alt="{html.escape(first["pages"][0]["alt"], quote=True)}" fetchpriority="high">\n'
            f'      </a>\n'
            f'      <div>\n'
            f'        <a class="btn" href="ep/{first["n"]}.html">開始閱讀 第{zh(first["n"])}話</a>\n'
            f'        <button class="btn ghost" id="inst" type="button">安裝到手機</button>\n'
            f'      </div>')
    if last is not first:
        hero += (f'\n      <p class="newest">最新：'
                 f'<a href="ep/{last["n"]}.html">第{zh(last["n"])}話 {last["title"]}</a></p>')
    splice('index.html', 'latest', hero)

    # sitemap
    urls = [f'  <url><loc>{BASE}</loc><lastmod>{EPS[-1]["date"]}</lastmod></url>']
    for ep in EPS:
        urls.append(f'  <url><loc>{BASE}ep/{ep["n"]}.html</loc><lastmod>{ep["date"]}</lastmod></url>')
    for c in CFG['characters']:
        urls.append(f'  <url><loc>{BASE}char/{c["slug"]}.html</loc>'
                    f'<lastmod>{EPS[-1]["date"]}</lastmod></url>')
    (ROOT / 'sitemap.xml').write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + '\n'.join(urls) + '\n</urlset>\n', 'utf-8')

    # sw.js:殼與暖快取清單
    shell = ["  './', './index.html',"]
    shell.append('  ' + ' '.join(f"'./ep/{e['n']}.html'," for e in EPS))
    shell.append('  ' + ' '.join(f"'./char/{c['slug']}.html'," for c in CFG['characters']))
    shell.append("  './style.css', './app.js', './manifest.json',")
    shell.append("  './assets/icon-192.png', './assets/icon-180.png', './assets/favicon-32.png'")
    splice('sw.js', 'shell', '\n'.join(shell))

    warm = []
    for ep in EPS:                    # 照閱讀順序暖:首頁的門口是第一話
        for p in ep['pages']:
            warm.append(f"./images/ep{ep['n']}/{p['f']}")
    warm += [f"./images/char-{c['slug']}.webp" for c in CFG['characters']]
    warm += ['./assets/icon-512.png', './assets/og.jpg']
    lines, cur = [], '  '
    for u in warm:
        item = f"'{u}', "
        if len(cur) + len(item) > 96:
            lines.append(cur.rstrip()); cur = '  '
        cur += item
    lines.append(cur.rstrip().rstrip(','))
    splice('sw.js', 'warm', '\n'.join(lines))

    # 版號 = 清單內容的 hash。人不用記得 bump,也不可能誤 bump:圖沒換
    # ASSET 就不會變,殼沒動 SHELL 就不會變。兩份清單各自算各自的。
    shell_files = (['index.html']
                   + [f'ep/{e["n"]}.html' for e in EPS]
                   + [f'char/{c["slug"]}.html' for c in CFG['characters']]
                   + ['style.css', 'app.js', 'manifest.json',
                      'assets/icon-192.png', 'assets/icon-180.png', 'assets/favicon-32.png'])
    splice('sw.js', 'ver',
           f"const SHELL = 'nt-shell-{EPOCH}-{digest(shell_files)}';\n"
           f"const ASSET = 'nt-asset-{EPOCH}-{digest(w[2:] for w in warm)}';")

    print(f'built {len(EPS)} episodes, {len(CFG["characters"])} characters')


if __name__ == '__main__':
    main()
