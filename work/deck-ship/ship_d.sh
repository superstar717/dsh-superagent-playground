#!/usr/bin/env bash
# ARCHIVE COPY — 运行时实例在 ~/src/ppt-recon-876f22c1685a/work/build/ship_d.sh（F240ppt 项目，
# 2026-11-14）。新项目复制本文件后改三处：NAME / DEST / authority 语料；其余门禁参数
#（expect/allow-bleed/min-notes/font/cite sources）按项目实际调整，不要删门禁。
# 本文件含本机路径，仅作归档示例；CI 只跑 selftest.py（与本目录的 deck_ship.py 等配套）。
# ship_d.sh — 本项目唯一的发货入口（AGENTS.md 硬约束 6；LESSONS E137）。
#
#   build(交付版) → build(QA 版) → render PDF/PNG → dump 文本 → deck-ship(门禁+原子复制+manifest)
#
# 用法:
#   bash work/build/ship_d.sh [--dest DIR] [--expect N] [--no-build] [--no-render]
# 退出码: 0 SHIPPED / 1 BLOCKED（交付目录保持不变）/ 2 用法错误
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE" || exit 2

NAME="<项目名>-D版"  # 归档示例：复制到项目后改成实际文件名
DEST="/Users/huweixing/project/F240ppt"
EXPECT=16
DO_BUILD=1
DO_RENDER=1
DECK_SHIP="${DECK_SHIP:-$HOME/.local/bin/deck-ship}"

while [ $# -gt 0 ]; do
  case "$1" in
    --dest) DEST="$2"; shift 2 ;;
    --expect) EXPECT="$2"; shift 2 ;;
    --no-build) DO_BUILD=0; shift ;;
    --no-render) DO_RENDER=0; shift ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) echo "ship_d: unknown arg $1" >&2; exit 2 ;;
  esac
done

mkdir -p ship render_ship "$DEST"
TS="$(date +%Y%m%d-%H%M%S)"
LOG="$HERE/ship/ship-$TS.log"
exec > >(tee -a "$LOG") 2>&1

echo "== ship_d.sh $(date '+%Y-%m-%d %H:%M:%S')  dest=$DEST  expect=$EXPECT  build=$DO_BUILD render=$DO_RENDER"
echo "== log: $LOG"

# ---------- 1/4 build ----------
if [ "$DO_BUILD" = "1" ]; then
  echo "==> [1/4] build delivery deck (font=微软雅黑; build_d.py runs deck-lint itself)"
  python3 build_d.py || { echo "== RESULT: BUILD FAILED"; exit 1; }
else
  echo "==> [1/4] build skipped (--no-build)"
fi

# ---------- 2/4 render ----------
PDF_COMPANION=()
if [ "$DO_RENDER" = "1" ]; then
  echo "==> [2/4] render QA PDF/PNG (Heiti SC build: macOS LibreOffice lacks 微软雅黑)"
  DECK_SUFFIX="-qa" DECK_FONT="Heiti SC" python3 build_d.py || { echo "== RESULT: QA BUILD FAILED"; exit 1; }
  rm -f render_ship/*.pdf render_ship/pg-*.png render_ship/总览.png
  /Applications/LibreOffice.app/Contents/MacOS/soffice --headless --convert-to pdf \
      --outdir render_ship "out/${NAME}-qa.pptx" >/dev/null 2>&1
  if [ -f "render_ship/${NAME}-qa.pdf" ]; then
    ( cd render_ship && pdftoppm -png -r 110 "${NAME}-qa.pdf" pg >/dev/null 2>&1 \
      && magick montage pg-*.png -tile 4x4 -geometry 640x360+3+3 -background '#cfcfcf' 总览.png >/dev/null 2>&1 )
    PDF_COMPANION=(--companion "render_ship/${NAME}-qa.pdf:${NAME}.pdf")
    echo "    PDF: render_ship/${NAME}-qa.pdf  (pages: $(ls render_ship/pg-*.png 2>/dev/null | wc -l | tr -d ' '))"
  else
    echo "    WARN: LibreOffice produced no PDF — shipping pptx only" >&2
  fi
else
  echo "==> [2/4] render skipped (--no-render); PDF companion will not be shipped"
fi

# ---------- 3/4 dump text for citation gate ----------
echo "==> [3/4] dump deck text for citation check"
python3 - "out/${NAME}.pptx" "ship/deck-text.txt" <<'PY'
import sys
from pptx import Presentation
prs = Presentation(sys.argv[1])
lines = []
for i, s in enumerate(prs.slides, 1):
    lines.append("\n=== slide %d ===" % i)
    for sh in s.shapes:
        if sh.has_text_frame and sh.text_frame.text.strip():
            lines.append(sh.text_frame.text.strip())
    if s.has_notes_slide and s.notes_slide.notes_text_frame.text.strip():
        lines.append("[NOTES] " + s.notes_slide.notes_text_frame.text.strip())
open(sys.argv[2], "w", encoding="utf-8").write("\n".join(lines) + "\n")
PY
echo "    $(wc -c < ship/deck-text.txt | tr -d ' ') bytes -> ship/deck-text.txt"

# ---------- 4/4 context + gates + ship ----------
echo "==> [4/4] gates + ship"
python3 - "$EXPECT" <<'PY'
import json, os, subprocess, sys
ctx = {
    "project": "F240ppt 病例汇报 PPT",
    "deck": "<实际pptx文件名>",
    "expected_slides": int(sys.argv[1]),
    "build_script": "work/build/build_d.py",
    "font_policy": "交付 pptx 仅微软雅黑；PDF 由 Heiti SC QA 构建渲染（macOS LibreOffice 缺微软雅黑）",
    "citation_sources": ["authority/guideline-OCR.md", "authority/original-deck.txt", "authority/lab-reports.md"],
    "cite_allowlist": "cite-allow.txt",
}
try:
    ctx["git_head"] = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
except Exception:
    pass
import time
ctx["at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
json.dump(ctx, open("ship/context.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
PY

SHIP_ARGS=("out/${NAME}.pptx" "$DEST"
  --expect "$EXPECT" --allow-bleed --min-notes 300
  --require-font "微软雅黑"
  --cite-draft ship/deck-text.txt
  --source authority/guideline-OCR.md
  --source authority/original-deck.txt
  --source authority/lab-reports.md
  --cite-allow cite-allow.txt
  --evidence-dir ship --context ship/context.json)
if [ "${#PDF_COMPANION[@]}" -gt 0 ]; then
  SHIP_ARGS+=("${PDF_COMPANION[@]}")
fi
"$DECK_SHIP" "${SHIP_ARGS[@]}"
rc=$?
if [ "$rc" = "0" ]; then
  echo "== RESULT: SHIPPED (deck-ship exit 0) — $DEST"
else
  echo "== RESULT: BLOCKED (deck-ship exit $rc) — delivery directory untouched"
fi
exit "$rc"
