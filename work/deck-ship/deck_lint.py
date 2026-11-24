#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""deck-lint: catch the deck defects that reach users.

Checks:
  1. slide count / 16:9 ratio
  2. shapes outside slide bounds (pictures may bleed with --allow-bleed)
  3. overlapping text boxes (relative-position edits break this silently)
  4. fonts used vs fonts installed (missing CJK font -> tofu on render)
  5. text too small (<7pt) or too many font families (>2)
  6. embedded media count and package size
  7. speaker-notes coverage

Usage:
  deck-lint deck.pptx [--allow-bleed] [--expect 16] [--min-notes 300] [--json]
Exit code 1 when a FAIL-level check fails, 0 otherwise (warnings allowed).
"""
import json
import os
import shutil
import subprocess
import sys
import zipfile

from pptx import Presentation
from pptx.util import Emu

FAIL, WARN, OK = "FAIL", "WARN", "OK"


def box(sh):
    return (Emu(sh.left).inches, Emu(sh.top).inches,
            Emu(sh.left).inches + Emu(sh.width).inches,
            Emu(sh.top).inches + Emu(sh.height).inches)


def installed_fonts():
    if not shutil.which("fc-list"):
        return None
    try:
        out = subprocess.run(["fc-list", ":", "family"], capture_output=True, text=True, timeout=20).stdout
        fams = set()
        for line in out.splitlines():
            for part in line.split(","):
                fams.add(part.strip())
        return fams
    except Exception:
        return None


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    path = argv[1]
    opts = {"allow_bleed": "--allow-bleed" in argv, "json": "--json" in argv,
            "expect": None, "min_notes": 0}
    if "--expect" in argv:
        opts["expect"] = int(argv[argv.index("--expect") + 1])
    if "--min-notes" in argv:
        opts["min_notes"] = int(argv[argv.index("--min-notes") + 1])

    prs = Presentation(path)
    slides = list(prs.slides)
    W, H = Emu(prs.slide_width).inches, Emu(prs.slide_height).inches
    report = {"file": path, "slides": len(slides), "size_in": [round(W, 3), round(H, 3)],
              "findings": [], "stats": {}}

    def add(level, code, msg, slide=None):
        report["findings"].append({"level": level, "code": code, "slide": slide, "msg": msg})

    # 1. count / ratio
    if opts["expect"] and len(slides) != opts["expect"]:
        add(FAIL, "slide-count", f"expected {opts['expect']} slides, got {len(slides)}")
    ratio = W / H if H else 0
    if abs(ratio - 16 / 9) > 0.02:
        add(WARN, "aspect", f"slide ratio {ratio:.3f} is not 16:9")

    fonts, notes_total, pics, vids = set(), 0, 0, 0
    for idx, s in enumerate(slides, 1):
        has_notes = s.has_notes_slide and s.notes_slide.notes_text_frame.text.strip()
        if has_notes:
            notes_total += len(s.notes_slide.notes_text_frame.text)
        texts = []
        for sh in s.shapes:
            try:
                if sh.shape_type == 13:
                    pics += 1
                elif sh.shape_type == 16:
                    vids += 1
            except Exception:
                pass
            if not (sh.width and sh.height):
                continue
            x, y, r, b = box(sh)
            if r > W + 0.05 or b > H + 0.05 or x < -0.05 or y < -0.05:
                is_pic = getattr(sh, "shape_type", None) == 13
                if not (opts["allow_bleed"] and is_pic):
                    add(WARN, "out-of-bounds",
                        f"{sh.name} reaches ({r:.2f},{b:.2f})in vs slide ({W:.2f},{H:.2f})", idx)
            if sh.has_text_frame:
                for p in sh.text_frame.paragraphs:
                    for run in p.runs:
                        if run.font.name:
                            fonts.add(run.font.name)
                        if run.font.size and run.font.size.pt < 7 and run.text.strip():
                            add(WARN, "tiny-text", f"{run.text.strip()[:14]!r} at {run.font.size.pt}pt", idx)
                if sh.text_frame.text.strip():
                    texts.append(sh)
        for a in range(len(texts)):
            for b2 in range(a + 1, len(texts)):
                ax1, ay1, ax2, ay2 = box(texts[a])
                bx1, by1, bx2, by2 = box(texts[b2])
                ox = max(0, min(ax2, bx2) - max(ax1, bx1))
                oy = max(0, min(ay2, by2) - max(ay1, by1))
                amin = min((ax2 - ax1) * (ay2 - ay1), (bx2 - bx1) * (by2 - by1))
                if ox > 0.12 and oy > 0.12 and amin and ox * oy / amin > 0.12:
                    add(WARN, "text-overlap",
                        f"{texts[a].text_frame.text[:16]!r} x {texts[b2].text_frame.text[:16]!r}", idx)

    # fonts installed?
    fams = installed_fonts()
    missing = []
    if fams:
        for f in sorted(fonts):
            if f and f not in fams and not any(f in x for x in fams):
                missing.append(f)
        if missing:
            add(WARN, "font-missing",
                f"fonts not installed: {missing} (macOS: build QA copy with a local font; deliverable keeps the original)")

    if len(fonts) > 2:
        add(WARN, "font-families", f"{len(fonts)} font families used: {sorted(fonts)}")
    if opts["min_notes"] and notes_total < opts["min_notes"]:
        add(FAIL, "notes", f"speaker notes only {notes_total} chars (< {opts['min_notes']})")
    size_mb = os.path.getsize(path) / 1e6
    if size_mb > 25:
        add(WARN, "size", f"package {size_mb:.1f} MB (>25 MB may exceed venue limits)")

    report["stats"] = {"fonts": sorted(fonts), "notes_chars": notes_total,
                       "pictures": pics, "videos": vids, "size_mb": round(size_mb, 2)}
    if opts["json"]:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"deck-lint  {path}")
        print(f"  slides {len(slides)}  size {W:.2f}x{H:.2f}in  pics {pics}  videos {vids}  "
              f"notes {notes_total} chars  {size_mb:.1f} MB")
        print(f"  fonts  {sorted(fonts)}")
        if not report["findings"]:
            print("  PASS  no findings")
        for f in report["findings"]:
            loc = f"p{f['slide']}" if f["slide"] else "-"
            print(f"  {f['level']:<4} {loc:>4}  {f['code']:<14} {f['msg']}")
        n_fail = sum(1 for f in report["findings"] if f["level"] == FAIL)
        n_warn = sum(1 for f in report["findings"] if f["level"] == WARN)
        print(f"  => {n_fail} fail / {n_warn} warn")
    return 1 if any(f["level"] == FAIL for f in report["findings"]) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
