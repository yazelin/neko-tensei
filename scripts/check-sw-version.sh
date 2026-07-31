#!/usr/bin/env bash
# sw.js 的 ASSET 版號只有在 images/ 真的變動時才准 bump。
#
# 為什麼:activate 會刪掉舊的 asset 快取,warm() 再用 cache:'reload' 整包重抓。
# 現在 images/ 是 14 MB,誤 bump 一次就是每個回訪讀者白抓 14 MB。這件事發生過
# 一次(差點),而且靠人記得,沒有機制擋。
#
# 反過來也要擋:images/ 動了卻沒 bump ASSET,讀者會拿到舊圖配新頁,更難發現。
#
# 跑法: scripts/check-sw-version.sh [base-ref]
#   base-ref 預設 origin/main。commit 前自己跑,或掛成 pre-push hook。
set -euo pipefail

BASE="${1:-origin/main}"
cd "$(dirname "$0")/.."

if ! git rev-parse --verify --quiet "$BASE" >/dev/null; then
  echo "找不到基準 $BASE,跳過檢查" >&2
  exit 0
fi

asset_of() { git show "$1:sw.js" 2>/dev/null | sed -n "s/^const ASSET = 'nt-asset-v\([0-9]*\)';/\1/p"; }

OLD=$(asset_of "$BASE")
NEW=$(sed -n "s/^const ASSET = 'nt-asset-v\([0-9]*\)';/\1/p" sw.js)

if [ -z "$OLD" ] || [ -z "$NEW" ]; then
  echo "讀不出 ASSET 版號(base=$OLD, now=$NEW),sw.js 的格式可能改了" >&2
  exit 1
fi

# --diff-filter 不加:改圖、加圖、刪圖都算變動
if git diff --quiet "$BASE" -- images/; then
  IMAGES_CHANGED=0
else
  IMAGES_CHANGED=1
fi

if [ "$IMAGES_CHANGED" = 0 ] && [ "$NEW" != "$OLD" ]; then
  echo "images/ 沒有任何變動,但 ASSET 從 v$OLD 被 bump 成 v$NEW。" >&2
  echo "這會讓每個回訪讀者重抓整包圖($(du -sh images | cut -f1))。" >&2
  echo "如果只是殼變了,請只 bump SHELL。" >&2
  exit 1
fi

if [ "$IMAGES_CHANGED" = 1 ] && [ "$NEW" = "$OLD" ]; then
  echo "images/ 有變動,但 ASSET 還停在 v$NEW。" >&2
  echo "讀者會拿到舊圖配新頁,而且不會有任何錯誤訊息。" >&2
  git diff --stat "$BASE" -- images/ >&2
  exit 1
fi

if [ "$IMAGES_CHANGED" = 1 ]; then
  echo "OK:images/ 有變動,ASSET v$OLD → v$NEW"
else
  echo "OK:images/ 沒變動,ASSET 維持 v$NEW"
fi
