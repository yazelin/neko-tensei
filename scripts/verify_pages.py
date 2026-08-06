#!/usr/bin/env python3
"""出圖後的視覺驗收:把每一頁交給視覺模型,照 story/verify.md 的規則判 PASS/FAIL。

    python3 scripts/verify_pages.py images/ep5/*.webp      # 驗指定的頁
    python3 scripts/verify_pages.py --regression           # 跑回歸集(改規則後必跑)

有任何一頁 FAIL 就 exit 1,方便接進別的流程。

**兩條後端,規則同一份。** 本機走 `codex exec`(要登入態的 Codex CLI);CI 上
沒有那個東西,改走 `.11` 的 codex-image-service `/v1/vision`——它底層跑的是
同一個 CLI、同一組帳號,金鑰就是出圖那把 `CODEX_IMAGE_KEY`。預設 `--backend
auto` 會依有沒有那個環境變數自己選,通常不用手動指定。

抓得到什麼、抓不到什麼,以及規則為什麼這樣寫,都在 story/verify.md。
"""
import argparse
import base64
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
RULES_DOC = ROOT / "story" / "verify.md"
CASES = ROOT / "scripts" / "verify_cases.txt"
MODEL = "gpt-5.6-luna"
VERDICT_RE = re.compile(r"VERDICT:\s*(PASS|FAIL)")


def load_rules():
    """取 story/verify.md 裡 <!-- RULES --> 之後的整段。

    規則跟說明放同一個檔,是為了讓「為什麼這樣寫」跟規則本身一起改;分兩個檔
    的話說明一定會過期。
    """
    text = RULES_DOC.read_text(encoding="utf-8")
    _, _, rules = text.partition("<!-- RULES -->")
    rules = rules.strip()
    if not rules:
        sys.exit(f"{RULES_DOC} 裡找不到 <!-- RULES --> 標記,規則讀不出來")
    return rules


def parse_cases(text):
    """回歸集文字 → [(git_spec, 期望, 說明)]。註解與空行跳過。"""
    cases = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        spec, want, *rest = line.split(None, 2)
        cases.append((spec, want, rest[0] if rest else ""))
    return cases


def verdict_of(output):
    """模型輸出 → PASS / FAIL / ERR。取最後一個,因為 codex 會把結尾重印一次。"""
    found = VERDICT_RE.findall(output)
    return found[-1] if found else "ERR"


def _with_context(rules, context):
    """把該頁的劇本接在規則後面。沒有劇本就原樣送出(規則 B 會自己跳過)。"""
    if not context:
        return rules
    return f"{rules}\n\n這一頁的劇本（規則 B 用這個對照）：\n{context}"


def check_page_service(image, rules, context=""):
    """走 .11 的 codex-image-service `/v1/vision`。CI 上唯一能用的路。

    GitHub Actions 沒有登入態的 Codex CLI,但那個服務有——它底層跑的是同一個
    CLI、同一組帳號。金鑰就是出圖那把 `CODEX_IMAGE_KEY`,不必另外生。
    """
    key = os.environ['CODEX_IMAGE_KEY']
    base = os.environ.get('CODEX_IMAGE_BASE_URL') or 'https://ching-tech.ddns.net/codex-image'
    body = json.dumps({
        'prompt': _with_context(rules, context),
        'images_base64': [base64.b64encode(pathlib.Path(image).read_bytes()).decode()],
    }).encode()
    req = urllib.request.Request(
        f'{base}/v1/vision', body,
        {'Content-Type': 'application/json', 'Authorization': f'Bearer {key}'})
    started = time.time()
    with urllib.request.urlopen(req, timeout=600) as f:
        text = json.load(f)['text']
    return verdict_of(text), time.time() - started, text


def pick_backend(name):
    """auto = 有 CODEX_IMAGE_KEY 就走服務,否則走本機 CLI。

    本機開發時通常沒設那個環境變數,自然落到 CLI;CI 上 workflow 會帶進來,
    自然落到服務。兩邊跑的是同一份規則、同一個底層模型。
    """
    if name == 'service' or (name == 'auto' and os.environ.get('CODEX_IMAGE_KEY')):
        return check_page_service
    return check_page


def check_page(image, rules, context=""):
    """跑一頁,回 (verdict, 秒數, 完整輸出)。"""
    started = time.time()
    # stdin 一定要關掉:codex exec 會等 stdin,不給就永遠掛著(不是模型慢)。
    proc = subprocess.run(
        ["codex", "exec", "--skip-git-repo-check", "--sandbox", "read-only",
         "-m", MODEL, "-c", 'model_reasoning_effort="medium"',
         "--image", str(image), "--", _with_context(rules, context)],
        capture_output=True, text=True, stdin=subprocess.DEVNULL,
    )
    output = proc.stdout + proc.stderr
    return verdict_of(output), time.time() - started, output


def storyboard_for(spec):
    """從案例的 git spec 找出同一版的分鏡,取出那一頁的劇本。

    規則 B(逐格對照說話者)要有劇本才成立。回歸集原本只餵圖,所以 B 永遠被跳過
    ——ep3/04 那個「老夫的台詞被畫成小鳥不啾」的案例因此測不到,放在集合裡等於
    白佔一格。圖與分鏡取同一個 ref,才不會拿新劇本對舊圖。
    """
    ref, _, path = spec.partition(":")
    m = re.match(r"images/ep(\d+)/(\d+)\.webp$", path)
    if not m:
        return ""            # 封面之類沒有對白的頁
    ep, page = m.groups()
    md = subprocess.run(["git", "show", f"{ref}:story/ep{ep}.md"], cwd=ROOT,
                        capture_output=True, text=True)
    if md.returncode != 0:
        return ""
    block = re.search(rf"^## {page}$.*?```\n(.*?)```", md.stdout, re.S | re.M)
    return block.group(1).strip() if block else ""


def run_regression(rules, verbose, check=None):
    cases = parse_cases(CASES.read_text(encoding="utf-8"))
    print(f"{'頁面':<28}{'期望':<8}{'實得':<8}{'秒':<6}結果")
    hits = []
    with tempfile.TemporaryDirectory() as tmp:
        for spec, want, note in cases:
            # 圖不進 repo,現場從 git 取。出包的版本本來就在歷史裡。
            blob = subprocess.run(["git", "show", spec], cwd=ROOT,
                                  capture_output=True)
            if blob.returncode != 0:
                sys.exit(f"取不到 {spec}:{blob.stderr.decode(errors='replace')[:200]}")
            image = pathlib.Path(tmp) / (spec.replace("/", "-").replace(":", "-"))
            image.write_bytes(blob.stdout)

            got, secs, output = (check or check_page)(
                image, rules, storyboard_for(spec))
            ok = got == want
            hits.append(ok)
            label = spec.split(":")[-1].replace("images/", "")
            print(f"{label:<28}{want:<8}{got:<8}{secs:>4.0f}s  "
                  f"{'ok' if ok else 'MISS'}  {'' if ok else note}")
            if verbose and not ok:
                print("  " + output.strip().replace("\n", "\n  ")[:800])
    print(f"\n命中 {sum(hits)} / {len(hits)}")
    return 0 if all(hits) else 1


def run_pages(paths, rules, verbose, check=None):
    failed = []
    for path in paths:
        got, secs, output = (check or check_page)(path, rules)
        print(f"{path}  {got}  {secs:.0f}s")
        if got != "PASS":
            failed.append(path)
            print("  " + output.strip().replace("\n", "\n  ")[-800:])
        elif verbose:
            print("  " + output.strip().replace("\n", "\n  ")[-400:])
    if failed:
        print(f"\n{len(failed)} 頁沒過:" + ", ".join(str(p) for p in failed))
        return 1
    print(f"\n{len(paths)} 頁全過")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pages", nargs="*", type=pathlib.Path, help="要驗的圖檔")
    ap.add_argument("--regression", action="store_true",
                    help="跑 scripts/verify_cases.txt 的回歸集")
    ap.add_argument("-v", "--verbose", action="store_true", help="印模型的完整判讀")
    ap.add_argument("--backend", choices=("auto", "cli", "service"), default="auto",
                    help="auto=有 CODEX_IMAGE_KEY 就走 .11 的服務,否則走本機 codex CLI")
    args = ap.parse_args(argv)

    rules = load_rules()
    check = pick_backend(args.backend)
    if args.regression:
        return run_regression(rules, args.verbose, check)
    if not args.pages:
        ap.error("給我圖檔路徑,或用 --regression")
    return run_pages(args.pages, rules, args.verbose, check)


if __name__ == "__main__":
    sys.exit(main())
