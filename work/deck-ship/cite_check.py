#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cite-check: every number in a draft must be findable in an authoritative source.

Motivation (LESSONS E136): a secondary digest (公众号二次整理) mixed in numbers that the
journal full text never contains. Checking by memory fails; checking by grep is cheap.

Usage:
  cite-check --draft draft.md --source a.md --source b.md [--show-lines N]
  cite-check --claim "DECRA mortality -18%" --source a.md
  cite-check --draft deck.txt --source a.md --json --fail-on-missing

Default exit 0 (it is a report); --fail-on-missing makes MISSING claims exit 1 so callers
(deck-ship) can turn the report into a gate. --json emits machine-readable claims with
status/hits for that purpose.

Caveat (keep quoting it): FOUND means the number+unit string exists in the source, NOT
that the sentence means the same thing (72h example in E136). MISSING is a strong signal:
either it has no source, or the OCR mangled it — verify before writing.
"""
import argparse
import hashlib
import json
import re
import sys

NUM = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(%|‰|ml|mL|L|mm|cm|m|g|mg|kg|h|min|s|d|天|年|月|岁|分|次|层|页|例|周)?(?![\w.])")


def claims(text):
    out, seen = [], set()
    for m in NUM.finditer(text):
        val, unit = m.group(1), m.group(2) or ""
        if not unit and len(val) < 2:
            continue
        key = f"{val}{unit}"
        if key in seen:
            continue
        seen.add(key)
        start = max(0, m.start() - 28)
        ctx = text[start:m.end() + 28].replace("\n", " ")
        out.append((key, val, unit, ctx.strip()))
    return out


def find_in(sources, val, unit):
    hits = []
    if unit:
        # adjacency required: "18 %" / "18%" / "18ml", never a bare "18" (avoids false FOUND)
        pats = [re.escape(val) + r"\s*" + re.escape(unit)]
    else:
        pats = [r"(?<![\d.])" + re.escape(val) + r"(?![\d])"]
    for path, lines in sources.items():
        for i, line in enumerate(lines, 1):
            if any(re.search(p, line) for p in pats):
                hits.append((path, i, line.strip()[:90]))
    return hits


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--draft")
    ap.add_argument("--claim", action="append", default=[])
    ap.add_argument("--source", action="append", default=[])
    ap.add_argument("--show-lines", type=int, default=1)
    ap.add_argument("--json", action="store_true", help="machine-readable output (for deck-ship)")
    ap.add_argument("--fail-on-missing", action="store_true",
                    help="exit 1 when any claim is MISSING (turns the report into a gate)")
    a = ap.parse_args()

    if not a.source:
        print("need at least one --source", file=sys.stderr)
        return 2
    sources = {}
    for p in a.source:
        with open(p, encoding="utf-8", errors="ignore") as f:
            sources[p] = f.read().splitlines()

    text = ""
    if a.draft:
        with open(a.draft, encoding="utf-8", errors="ignore") as f:
            text = f.read()
    text += "\n" + "\n".join(a.claim)

    rows = claims(text)
    checked = []
    missing = 0
    for key, val, unit, ctx in rows:
        hits = find_in(sources, val, unit)
        status = "FOUND" if hits else "MISSING"
        if not hits:
            missing += 1
        checked.append({
            "key": key, "val": val, "unit": unit, "ctx": ctx[:90], "status": status,
            "hits": [{"path": p, "line": i, "text": t} for p, i, t in hits[:a.show_lines]],
        })

    if a.json:
        report = {
            "draft": a.draft,
            "claims": a.claim,
            "sources": [{"path": p, "sha256": sha256(p), "lines": len(sources[p])} for p in a.source],
            "checked": checked,
            "total": len(checked),
            "n_missing": missing,
            "missing": [c["key"] for c in checked if c["status"] == "MISSING"],
        }
        if a.draft:
            report["draft_sha256"] = sha256(a.draft)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1 if (a.fail_on_missing and missing) else 0

    if not rows:
        print("no numeric claims found")
        return 0
    print(f"{'claim':<12} {'status':<10} evidence")
    for c in checked:
        if c["status"] == "FOUND":
            ev = "; ".join(f"{h['path'].split('/')[-1]}:{h['line']}" for h in c["hits"])
            print(f"{c['key']:<12} {'FOUND':<10} {ev}")
        else:
            print(f"{c['key']:<12} {'MISSING':<10} <- {c['ctx'][:70]}")
    print(f"\n{len(rows)} claims, {missing} missing from {len(sources)} source file(s)")
    print("note: FOUND means the number+unit string exists in the source, NOT that the")
    print("      sentence means the same thing. MISSING means it must not be written.")
    return 1 if (a.fail_on_missing and missing) else 0


if __name__ == "__main__":
    sys.exit(main())
