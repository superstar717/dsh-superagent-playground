# -*- coding: utf-8 -*-
"""F240ppt deck — F 版：把 E 版内容整体迁移到大赛官方规定模板（template_a.pptx）上。

用户 2026-11-16 追加要求："模板没换，把模板换成我发的比赛规定模板"——即 deck 必须长在
官方模板（白底、顶部居中深青 #074B6E 标题）上，而不是保留 D/E 的深色设计。

做法：以 official-template.pptx（= 用户发的比赛规定模板 template_a.pptx）为基底文件
（继承官方母版/版式），逐页读取 E 版（内容与版式已调好：放大字体、讨论页入术前、
备注 1269 字），按"换肤规则"重画：
  - 顶部深色标题带/整页深底 → 删除，改为官方样式：居中小眉题 + 居中青色标题
  - 深色结论条/图注条/数据砖/雪佛龙 → 浅青底色块（#EEF6F9），深色文字
  - 白字/浅蓝字 → 深青或深灰（按字号/位置判定）
  - 红色 ↑/↓、绿色达标值 → 保留
  - 小装饰图标（<0.5in）→ 删除；图片/视频原位迁移
  - 备注原样复制；页序与 E 版一致

用法:
  python3 build_f.py            # 交付版（微软雅黑）
  DECK_SUFFIX=-qa DECK_FONT="Heiti SC" python3 build_f.py
退出码: 0 成功 / 1 失败。
"""
import copy
import os
import subprocess
import sys
import tempfile

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR, MSO_AUTO_SIZE
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.oxml.ns import qn

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(HERE, "official-template.pptx")
EDECK = os.environ.get("CONTENT_DECK",
                       os.path.join(HERE, "out", "2026武威市神经外科诊疗技能大赛病例汇报-E版.pptx"))
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)
FONT = os.environ.get("DECK_FONT", "微软雅黑")
SUFFIX = os.environ.get("DECK_SUFFIX", "")
NAME = "2026武威市神经外科诊疗技能大赛病例汇报-F版"
DST = os.path.join(OUT, f"{NAME}{SUFFIX}.pptx")

TEAL = RGBColor.from_string("074B6E")      # 官方模板标题色
INK = RGBColor.from_string("17272F")
BODY = RGBColor.from_string("33424B")
MUTED = RGBColor.from_string("5F7280")
KICK = RGBColor.from_string("3E7391")
BAR_TXT = RGBColor.from_string("1F3A47")
TINT = "EEF6F9"
HAIR = "D8E3E9"
RED = RGBColor.from_string("B42318")
GREEN = RGBColor.from_string("0F7A4F")
ACC = RGBColor.from_string("0E5A78")

LIGHTS = {"FFFFFF", "B9CED6", "8FC3D2", "BBD3DB", "AFC0C7", "8FA9B5", "DCE5EA"}
DARKS_KEEP = {"33424B", "0A1A23", "7C8B94", "B42318", "0F7A4F", "0F6E6A", "0E5A78"}

PAGENO = 17


def rgb(r):
    return RGBColor.from_string(r.lstrip("#"))


def run_color(r):
    try:
        if r.font.color is not None and r.font.color.type is not None:
            return str(r.font.color.rgb)
    except Exception:
        pass
    return None


def map_color(r, cur, size, is_title):
    if cur is None:
        return BODY if size and size >= 13 else MUTED
    cu = cur.upper()
    if cu == "B42318":
        return RED
    if cu in ("0F7A4F", "0F6E6A"):
        return GREEN if cu == "0F7A4F" else ACC
    if cu in DARKS_KEEP:
        return RGBColor.from_string(cu)
    if cu in LIGHTS:
        if is_title:
            return TEAL
        if size and size >= 24:
            return TEAL
        return BAR_TXT
    return RGBColor.from_string(cu)


def clear_slides(prs):
    """彻底移除模板自带幻灯片：删 sldId + 删 presentation part 的 rel（防孤儿 part）。"""
    sldIdLst = prs.slides._sldIdLst
    for sid in list(sldIdLst):
        rId = sid.get(qn("r:id"))
        try:
            prs.part.drop_rel(rId)
        except Exception:
            pass
        sldIdLst.remove(sid)


def blank_layout(prs):
    for lay in prs.slide_masters[0].slide_layouts:
        if lay.name in ("空白", "Blank"):
            return lay
    return prs.slide_masters[0].slide_layouts[-1]


def add_rect(s, x, y, w, h, fill=TINT, line=None):
    sh = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.shadow.inherit = False
    sh.fill.solid()
    sh.fill.fore_color.rgb = rgb(fill)
    if line:
        sh.line.color.rgb = rgb(line)
        sh.line.width = Pt(0.75)
    else:
        sh.line.fill.background()
    el = sh._element
    for ch in list(el):
        if ch.tag.endswith("}style"):
            el.remove(ch)
    return sh


def add_line(s, x1, y1, x2, y2, color=HAIR, lw=0.75):
    conn = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1),
                                  Inches(x2), Inches(y2))
    conn.line.color.rgb = rgb(color)
    conn.line.width = Pt(lw)
    el = conn._element
    for ch in list(el):
        if ch.tag.endswith("}style"):
            el.remove(ch)
    return conn


def is_title_run(page_idx, sh, size):
    """标题判定：页面顶部(y<0.9)的大字号文字。"""
    try:
        y = Emu(sh.top).inches
    except Exception:
        return False
    return y < 0.95 and size is not None and size >= 24


def transfer_text(s, sh, page_idx):
    tf = sh.text_frame
    try:
        x, y = Emu(sh.left).inches, Emu(sh.top).inches
        w, h = Emu(sh.width).inches, Emu(sh.height).inches
    except Exception:
        return None
    anchor = tf.vertical_anchor if tf.vertical_anchor is not None else MSO_ANCHOR.TOP
    # 标题重排：居中到页首
    sizes = [r.font.size.pt for p in tf.paragraphs for r in p.runs if r.font.size]
    txt0 = tf.text.strip()
    title = is_title_run(page_idx, sh, max(sizes) if sizes else None) and w > 6
    kicker = txt0.startswith("PART ") and not title and y < 1.3
    if title:
        x, y, w = 0.85, 0.40, 11.63
    if kicker:
        x, y, w = 0.85, 0.10, 11.63
    if page_idx == 1:
        # 封面：右侧有 CT 图——大赛名通栏居中，病例标题限左半区；大标题降 36pt 防溢出
        mx = max(sizes) if sizes else 0
        if mx >= 24:
            x, w = 0.85, 6.6
        else:
            x, y, w = 0.85, 0.55, 11.63
    if page_idx == 17:
        x, w = 0.85, 11.63
    b = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    ntf = b.text_frame
    ntf.word_wrap = True
    ntf.auto_size = MSO_AUTO_SIZE.NONE
    ntf.vertical_anchor = anchor
    for m in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(ntf, m, 0)
    first = True
    for p in tf.paragraphs:
        np = ntf.paragraphs[0] if first else ntf.add_paragraph()
        first = False
        if p.alignment is not None:
            np.alignment = p.alignment
        if title or kicker or page_idx in (1, 17):
            np.alignment = PP_ALIGN.CENTER
        if p.line_spacing is not None:
            np.line_spacing = p.line_spacing
        for r in p.runs:
            if not r.text:
                continue
            nr = np.add_run()
            nr.text = r.text
            f = nr.font
            f.name = FONT
            size = r.font.size.pt if r.font.size else 14
            if kicker:
                size = min(size, 13)
            if page_idx == 1 and size >= 36:
                size = 36
            f.size = Pt(size)
            f.bold = bool(r.font.bold) or title
            cur = run_color(r)
            if kicker:
                f.color.rgb = KICK
            else:
                f.color.rgb = map_color(page_idx, cur, size, title)
            if r._r.find(qn("a:rPr")) is not None:
                spc = r._r.find(qn("a:rPr")).get("spc")
                if spc:
                    nr._r.get_or_add_rPr().set("spc", spc)
        if not np.runs:
            np.add_run().text = ""
    return b


def transfer_autoshape(s, sh, page_idx):
    """自动形状：顶部标题带/整页深底 → 删；其余 → 浅色块（含文字则连同重排）。"""
    try:
        x, y = Emu(sh.left).inches, Emu(sh.top).inches
        w, h = Emu(sh.width).inches, Emu(sh.height).inches
    except Exception:
        return None
    if w > 12.5 and y < 1.2:      # 顶部标题带
        return None
    if w > 13 and h > 7:          # 整页深底
        return None
    txt = sh.text_frame.text.strip() if sh.has_text_frame else ""
    if txt:
        # 雪佛龙/带文字的形状：浅色块 + 内部文字重排
        rect = add_rect(s, x, y, w, h, fill=TINT)
        rtf = rect.text_frame
        rtf.word_wrap = True
        rtf.margin_left = rtf.margin_right = Inches(0.05)
        rtf.margin_top = rtf.margin_bottom = 0
        rtf.vertical_anchor = MSO_ANCHOR.MIDDLE
        first = True
        for p in sh.text_frame.paragraphs:
            np = rtf.paragraphs[0] if first else rtf.add_paragraph()
            first = False
            np.alignment = PP_ALIGN.CENTER
            if p.line_spacing is not None:
                np.line_spacing = p.line_spacing
            for r in p.runs:
                if not r.text:
                    continue
                nr = np.add_run()
                nr.text = r.text
                nr.font.name = FONT
                size = r.font.size.pt if r.font.size else 14
                nr.font.size = Pt(size)
                cur = run_color(r)
                nr.font.color.rgb = map_color(page_idx, cur, size, False)
                nr.font.bold = bool(r.font.bold)
        return rect
    fill = "F2F6F8"
    return add_rect(s, x, y, w, h, fill=fill)


def main():
    base = Presentation(BASE)
    content = Presentation(EDECK)
    tmpfiles = []

    clear_slides(base)
    lay = blank_layout(base)

    for page_idx, eslide in enumerate(content.slides, 1):
        s = base.slides.add_slide(lay)
        # 先画形状（色块在底层），再画文字与图片
        pending = []
        for sh in eslide.shapes:
            st = sh.shape_type
            if st == 6:  # group：平铺处理
                for sub in sh.shapes:
                    pending.append(sub)
                continue
            pending.append(sh)

        # 分两轮：第一轮色块与线，第二轮文字/图片/媒体（保证文字在上层）
        rects, texts, pics = [], [], []
        for sh in pending:
            st = str(sh.shape_type)
            if st.startswith("AUTO_SHAPE"):
                r = transfer_autoshape(s, sh, page_idx)
                if r is not None:
                    rects.append(r)
            elif st.startswith("LINE"):
                try:
                    add_line(s, Emu(sh.left).inches, Emu(sh.top).inches,
                             Emu(sh.left).inches + Emu(sh.width).inches,
                             Emu(sh.top).inches + Emu(sh.height).inches,
                             color=HAIR, lw=0.75)
                except Exception:
                    pass
            elif st.startswith("TEXT"):
                texts.append(sh)
            elif st.startswith("PICTURE"):
                pics.append(sh)
            elif st.startswith("MEDIA"):
                pics.append(sh)

        for sh in texts:
            transfer_text(s, sh, page_idx)
        for sh in pics:
            try:
                x, y = Emu(sh.left).inches, Emu(sh.top).inches
                w, h = Emu(sh.width).inches, Emu(sh.height).inches
            except Exception:
                continue
            if w < 0.5 and h < 0.5:
                continue  # 小装饰图标不迁
            st = str(sh.shape_type)
            if st.startswith("MEDIA") and os.environ.get("F_NO_MOVIES") != "1":
                # 视频：从 XML 里取 videoFile 与海报
                el = sh._element
                vid = el.find(".//" + qn("a:videoFile"))
                blob = None
                poster = None
                if vid is not None:
                    rid = vid.get(qn("r:link"))
                    blob = eslide.part.rels[rid].target_part.blob
                blip = el.find(".//" + qn("a:blip"))
                if blip is not None:
                    brid = blip.get(qn("r:embed"))
                    try:
                        poster = eslide.part.rels[brid].target_part.blob
                    except Exception:
                        poster = None
                vpath = ppath = None
                if blob:
                    vf = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
                    vf.write(blob)
                    vf.close()
                    vpath = vf.name
                    tmpfiles.append(vpath)
                if poster:
                    pf = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                    pf.write(poster)
                    pf.close()
                    ppath = pf.name
                    tmpfiles.append(ppath)
                try:
                    s.shapes.add_movie(vpath, Inches(x), Inches(y), Inches(w), Inches(h),
                                       poster_frame_image=ppath, mime_type="video/mp4")
                except Exception as exc:
                    print(f"  WARN p{page_idx} 视频迁移失败: {exc}")
            else:
                try:
                    import io
                    s.shapes.add_picture(io.BytesIO(sh.image.blob), Inches(x), Inches(y),
                                         Inches(w), Inches(h))
                except Exception as exc:
                    print(f"  WARN p{page_idx} 图片迁移失败: {exc}")

        # 备注
        if eslide.has_notes_slide:
            s.notes_slide.notes_text_frame.text = eslide.notes_slide.notes_text_frame.text.strip()

    base.save(DST)
    print(f"built {DST} ({os.path.getsize(DST)/1048576:.1f} MB)")
    for p in tmpfiles:
        try:
            os.unlink(p)
        except Exception:
            pass

    lint = os.path.expanduser("~/.local/deck-lint/deck_lint.py")
    rc = subprocess.run([sys.executable, lint, DST, "--min-notes", "300"]).returncode
    if rc:
        print("== RESULT: BUILD FAILED (deck-lint FAIL)")
        return 1
    print("== RESULT: BUILD OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
