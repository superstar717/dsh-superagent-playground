#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stamp a light diagonal tiled watermark on every page of a PDF.

usage: watermark_pdf.py IN.pdf OUT.pdf ["text"]

reportlab draws the overlay (arbitrary rotation + alpha, built-in CJK CID font),
pypdf merges it onto each page. Body text stays readable: alpha 0.10, grey.
"""
import io
import os
import sys

from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import Color
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))


def overlay(width, height, text):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(width, height))
    WM_SIZE = float(os.environ.get("WATERMARK_SIZE", "22"))
    c.setFont("STSong-Light", WM_SIZE)
    # draw twice: dark ink (visible on white pages) + white ink (visible on dark pages);
    # each is invisible on the opposite background, so one pass covers both.
    colors = [Color(0.32, 0.38, 0.42), Color(1, 1, 1)]
    step_x, step_y = 640, 280
    row = 0
    y = -60
    while y < height + 80:
        x = -160 + (row % 2) * (step_x / 2)
        while x < width + 60:
            for col in colors:
                c.saveState()
                c.translate(x, y)
                c.rotate(32)
                c.setFillColor(col)
                c.setFillAlpha(float(os.environ.get("WATERMARK_ALPHA", "0.14")))
                c.drawString(0, 0, text)
                c.restoreState()
            x += step_x
        y += step_y
        row += 1
    c.save()
    buf.seek(0)
    return PdfReader(buf).pages[0]


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    src, dst = sys.argv[1], sys.argv[2]
    text = sys.argv[3] if len(sys.argv) > 3 else "2026 武威市神经外科诊疗技能大赛"
    reader = PdfReader(src)
    writer = PdfWriter()
    for page in reader.pages:
        w = float(page.mediabox.width)
        h = float(page.mediabox.height)
        page.merge_page(overlay(w, h, text))
        writer.add_page(page)
    with open(dst, "wb") as f:
        writer.write(f)
    print("watermarked: %s (%d pages)" % (dst, len(reader.pages)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
