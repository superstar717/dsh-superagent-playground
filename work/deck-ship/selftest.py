#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""deck-ship selftest — positive AND negative paths, including "blocked means nothing copied".

Run locally:  python3 ~/.local/deck-ship/selftest.py
Run in CI:    DECK_SHIP=.../deck_ship.py DECK_LINT=.../deck_lint.py CITE_CHECK=.../cite_check.py

Every case asserts on exit code, stdout status, destination contents and manifest — the
E44 rule: "配置写完 + 单测过" does not prove the gate blocks; the negative path must show
the delivery directory stayed empty.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

from pptx import Presentation
from pptx.util import Inches, Pt

HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser("~")


def tool(path):
    return os.path.abspath(path)


def pick(env, local_default, sibling):
    path = os.environ.get(env) or (sibling if os.path.exists(sibling) else local_default)
    return tool(path)


SHIP = pick("DECK_SHIP", os.path.join(HOME, ".local/deck-ship/deck_ship.py"),
            os.path.join(HERE, "deck_ship.py"))
LINT = pick("DECK_LINT", os.path.join(HOME, ".local/deck-lint/deck_lint.py"),
            os.path.join(HERE, "deck_lint.py"))
CITE = pick("CITE_CHECK", os.path.join(HOME, ".local/cite-check/cite_check.py"),
            os.path.join(HERE, "cite_check.py"))

PASSED, FAILED = [], []


def check(name, cond, detail=""):
    if cond:
        PASSED.append(name)
        print("PASS  %s" % name)
    else:
        FAILED.append(name)
        print("FAIL  %s  %s" % (name, detail))


def make_deck(path, slides=2, notes_chars=400, font="Arial", overlap=False):
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    blank = prs.slide_layouts[6]
    for i in range(slides):
        s = prs.slides.add_slide(blank)
        box = s.shapes.add_textbox(Inches(0.8), Inches(0.8), Inches(6.0), Inches(1.2))
        run = box.text_frame.paragraphs[0].add_run()
        run.text = "第 %d 页 标题" % (i + 1)
        run.font.size = Pt(24)
        run.font.name = font
        if overlap:
            second = s.shapes.add_textbox(Inches(1.0), Inches(1.0), Inches(4.0), Inches(1.0))
            run2 = second.text_frame.paragraphs[0].add_run()
            run2.text = "重叠区块"
            run2.font.size = Pt(18)
            run2.font.name = font
        notes = s.notes_slide.notes_text_frame
        notes.text = ("讲稿" * (notes_chars // 2 + 1))[:notes_chars]
    prs.save(path)
    return path


def make_source(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def run_ship(args, env):
    proc = subprocess.run([sys.executable, SHIP] + args, capture_output=True, text=True,
                          timeout=180, env=env)
    try:
        data = json.loads(proc.stdout)
    except ValueError:
        data = None
    return proc, data


def main():
    base = tempfile.mkdtemp(prefix="deck-ship-selftest-")
    env = dict(os.environ, DECK_LINT=LINT, CITE_CHECK=CITE)
    good = make_deck(os.path.join(base, "good.pptx"))
    bad_overlap = make_deck(os.path.join(base, "overlap.pptx"), overlap=True)
    src_ok = make_source(os.path.join(base, "source-ok.md"), "硬膜外血肿 18% 的病例需要手术。\n")
    src_no = make_source(os.path.join(base, "source-no.md"), "本条来源不含任何百分数。\n")
    draft_ok = make_source(os.path.join(base, "draft-ok.md"), "本组病死率 18%。\n")
    draft_bad = make_source(os.path.join(base, "draft-bad.md"), "本组病死率 19%。\n")

    try:
        # 1. positive: good deck ships, hash + manifest recorded
        dest = os.path.join(base, "d1")
        proc, data = run_ship([good, dest, "--expect", "2", "--min-notes", "300",
                               "--require-font", "Arial", "--json"], env)
        manifest = os.path.join(dest, "good.ship-manifest.json")
        ok = (proc.returncode == 0 and data and data.get("status") == "SHIPPED"
              and os.path.isfile(os.path.join(dest, "good.pptx")) and os.path.isfile(manifest))
        detail = proc.stdout[-400:] + proc.stderr[-300:]
        if ok:
            man = json.load(open(manifest, encoding="utf-8"))
            import hashlib
            digest = hashlib.sha256(open(os.path.join(dest, "good.pptx"), "rb").read()).hexdigest()
            ok = man["status"] == "SHIPPED" and man["files"][0]["sha256"] == digest
            detail = json.dumps(man["files"], ensure_ascii=False)
        check("positive: good deck is SHIPPED with manifest and matching hash", ok, detail)

        # 2. negative: wrong --expect blocks and leaves dest EMPTY (no files, no manifest)
        dest = os.path.join(base, "d2")
        proc, data = run_ship([good, dest, "--expect", "3", "--json"], env)
        left = sorted(os.listdir(dest)) if os.path.isdir(dest) else []
        check("negative: wrong --expect is BLOCKED and dest stays empty",
              proc.returncode == 1 and data and data.get("status") == "BLOCKED" and left == [],
              "rc=%s status=%s left=%s\n%s" % (proc.returncode,
                                              data and data.get("status"), left, proc.stdout[-300:]))

        # 3. negative: notes below --min-notes blocks (lint FAIL, not just a warning)
        dest = os.path.join(base, "d3")
        proc, data = run_ship([good, dest, "--min-notes", "99999", "--json"], env)
        left = sorted(os.listdir(dest)) if os.path.isdir(dest) else []
        check("negative: short notes is BLOCKED and dest stays empty",
              proc.returncode == 1 and data.get("status") == "BLOCKED" and left == [],
              proc.stdout[-300:])

        # 4. negative: shipping the QA-font build under a project font requirement is blocked
        dest = os.path.join(base, "d4")
        proc, data = run_ship([good, dest, "--require-font", "微软雅黑", "--json"], env)
        left = sorted(os.listdir(dest)) if os.path.isdir(dest) else []
        check("negative: wrong font is BLOCKED (catches shipping the QA build)",
              proc.returncode == 1 and data.get("status") == "BLOCKED" and left == [],
              proc.stdout[-300:])

        # 5. negative: unsourced number blocks the ship
        dest = os.path.join(base, "d5")
        proc, data = run_ship([good, dest, "--cite-draft", draft_bad, "--source", src_no,
                               "--json"], env)
        left = sorted(os.listdir(dest)) if os.path.isdir(dest) else []
        check("negative: unsourced number is BLOCKED and dest stays empty",
              proc.returncode == 1 and data.get("status") == "BLOCKED" and left == [],
              proc.stdout[-400:])

        # 6. positive: sourced number passes the cite gate
        dest = os.path.join(base, "d6")
        proc, data = run_ship([good, dest, "--cite-draft", draft_ok, "--source", src_ok,
                               "--json"], env)
        check("positive: sourced number passes cite gate",
              proc.returncode == 0 and data.get("status") == "SHIPPED",
              proc.stdout[-300:] + proc.stderr[-300:])

        # 7. positive: explicit allowlist entry with a reason passes; blocking list empty
        dest = os.path.join(base, "d7")
        allow = make_source(os.path.join(base, "allow.txt"),
                            "%s # 单测：来源缺失但已人工确认\n" % "19%")
        proc, data = run_ship([good, dest, "--cite-draft", draft_bad, "--source", src_ok,
                               "--cite-allow", allow, "--json"], env)
        check("positive: allowlisted missing claim passes and is recorded",
              proc.returncode == 0 and data.get("status") == "SHIPPED"
              and data.get("cite", {}).get("allowed") == ["19%"],
              proc.stdout[-400:])

        # 8. negative: allowlist without a reason is a gate error, not a silent bypass
        dest = os.path.join(base, "d8")
        bad_allow = make_source(os.path.join(base, "allow-bad.txt"), "19%\n")
        proc, data = run_ship([good, dest, "--cite-draft", draft_bad, "--source", src_ok,
                               "--cite-allow", bad_allow, "--json"], env)
        left = sorted(os.listdir(dest)) if os.path.isdir(dest) else []
        check("negative: allowlist without reason is BLOCKED",
              proc.returncode == 1 and data.get("status") == "BLOCKED" and left == [],
              proc.stdout[-300:])

        # 9. companion file is shipped and hashed
        dest = os.path.join(base, "d9")
        pdf = make_source(os.path.join(base, "deck.pdf"), "fake pdf")
        proc, data = run_ship([good, dest, "--companion", pdf + ":goods.pdf", "--json"], env)
        man = json.load(open(os.path.join(dest, "good.ship-manifest.json"), encoding="utf-8"))
        check("companion: renamed companion lands in dest and manifest",
              proc.returncode == 0 and os.path.isfile(os.path.join(dest, "goods.pdf"))
              and [f["name"] for f in man["files"]] == ["good.pptx", "goods.pdf"],
              proc.stdout[-300:])

        # 9b. a deck-only --verify-only keeps the companion a previous manifest recorded
        #     (re-hashed, never silently dropped); tampering it turns the verify into BLOCKED
        proc2, data2 = run_ship([good, dest, "--verify-only", "--json"], env)
        man2 = json.load(open(os.path.join(dest, "good.ship-manifest.json"), encoding="utf-8"))
        actions = {f["name"]: f["action"] for f in man2["files"]}
        keep_ok = (proc2.returncode == 0 and data2.get("status") == "VERIFIED"
                   and actions.get("goods.pdf") == "kept" and len(man2["files"]) == 2)
        with open(os.path.join(dest, "goods.pdf"), "ab") as f:
            f.write(b"tamper")
        proc3, data3 = run_ship([good, dest, "--verify-only", "--json"], env)
        check("verify-only: deck-only verify keeps recorded companion, tamper is BLOCKED",
              keep_ok and proc3.returncode == 1 and data3.get("status") == "BLOCKED",
              "keep=%s actions=%s tamper_rc=%s\n%s"
              % (keep_ok, actions, proc3.returncode, proc3.stdout[-300:]))

        # 10. verify-only adopts an existing identical delivery, rejects a modified one
        dest = os.path.join(base, "d10")
        os.makedirs(dest)
        shutil.copyfile(good, os.path.join(dest, "good.pptx"))
        proc, data = run_ship([good, dest, "--verify-only", "--json"], env)
        man = os.path.join(dest, "good.ship-manifest.json")
        ok = (proc.returncode == 0 and data.get("status") == "VERIFIED"
              and os.path.isfile(man))
        with open(os.path.join(dest, "good.pptx"), "ab") as f:
            f.write(b"tamper")
        proc2, data2 = run_ship([good, dest, "--verify-only", "--json"], env)
        check("verify-only: adopts identical file, rejects tampered file",
              ok and proc2.returncode == 1 and data2.get("status") == "BLOCKED",
              "adopt=%s tamper_rc=%s\n%s" % (ok, proc2.returncode, proc2.stdout[-300:]))

        # 11. dry-run runs gates but copies/writes nothing
        dest = os.path.join(base, "d11")
        proc, data = run_ship([good, dest, "--dry-run", "--json"], env)
        left = sorted(os.listdir(dest)) if os.path.isdir(dest) else []
        check("dry-run: gates run, nothing copied, no manifest",
              proc.returncode == 0 and data.get("status") == "WOULD-SHIP" and left == [],
              proc.stdout[-300:])

        # 12. overlap is reported as WARN by deck-lint (regression: does not block by itself),
        #     but the manifest surfaces it so a human still sees it
        dest = os.path.join(base, "d12")
        proc, data = run_ship([bad_overlap, dest, "--json"], env)
        man = json.load(open(os.path.join(dest, "overlap.ship-manifest.json"), encoding="utf-8"))
        codes = [f["code"] for f in man["lint"]["findings"]]
        check("overlap: WARN is shipped+recorded (blocking is reserved for FAIL)",
              proc.returncode == 0 and "text-overlap" in codes,
              json.dumps(codes))
    finally:
        shutil.rmtree(base, ignore_errors=True)

    print("\n%d passed, %d failed" % (len(PASSED), len(FAILED)))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
