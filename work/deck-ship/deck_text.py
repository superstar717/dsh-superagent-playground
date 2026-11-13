#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""deck_text.py — dump every text block of a .pptx (shapes, tables, notes) for cite-check.

Why a dump: the citation gate (LESSONS E136) must run on what the deck actually says,
not on the build source. One number per line is NOT required — cite-check extracts
"number + unit" claims from the whole text.

Usage:
  python3 deck_text.py deck.pptx > deck.txt
  python3 deck_text.py --no-notes deck.pptx > visible-only.txt
"""
import sys

from pptx import Presentation


def dump(path, include_notes=True):
    prs = Presentation(path)
    parts = []
    for idx, slide in enumerate(prs.slides, 1):
        parts.append("\n=== slide %d ===" % idx)
        for shape in slide.shapes:
            try:
                if shape.has_text_frame and shape.text_frame.text.strip():
                    parts.append(shape.text_frame.text.strip())
            except AttributeError:
                pass
            if getattr(shape, "has_table", False):
                for row in shape.table.rows:
                    cells = [c.text.strip() for c in row.cells]
                    if any(cells):
                        parts.append(" | ".join(cells))
        if include_notes and slide.has_notes_slide:
            notes = slide.notes_slide.notes_text_frame.text.strip()
            if notes:
                parts.append("[NOTES] " + notes)
    return "\n".join(parts)


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        print(__doc__)
        return 2
    print(dump(args[0], include_notes="--no-notes" not in argv))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
