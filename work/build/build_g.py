# -*- coding: utf-8 -*-
"""F240ppt — 规定模板版：把 E 版内容放进用户发的比赛规定模板的"素颜"样式里。

用户两轮反馈后（2026-11-16）的最严格解读：deck 每一页都要长成官方模板的样子——
  * 页首大标题 = 官方模板的章节名（病历简介 / 术前影像 / 术前准备 / 术中操作 /
    术后情况 / 中长期随访 / 总结；讨论页 = 术前讨论一/二），居中、深青 #074B6E、加粗；
  * 章节名下放一行灰色小字（原 E 版页面导语，信息不丢）；
  * 正文一律纯文本（无色块/无栏目框/无装饰条）；化验表保留浅灰行线；图片/视频原位；
  * 官方模板没有的页面（目录、致谢）不保留；整册 15 页。
基底文件 = official-template.pptx（用户发的比赛规定模板）。

用法:
  python3 build_g.py            # 交付版（微软雅黑）
  DECK_SUFFIX=-qa DECK_FONT="Heiti SC" python3 build_g.py
退出码: 0 成功 / 1 失败。
"""
import io
import os
import re
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
NAME = "2026武威市神经外科诊疗技能大赛病例汇报-规定模板版"
DST = os.path.join(OUT, f"{NAME}{SUFFIX}.pptx")

TEAL = RGBColor.from_string("074B6E")
INK = RGBColor.from_string("17272F")
BODY = RGBColor.from_string("333B41")
MUTED = RGBColor.from_string("6B7880")
RED = RGBColor.from_string("B42318")
GREEN = RGBColor.from_string("0F7A4F")
ACC = RGBColor.from_string("0E5A78")
HAIR = "D9D9D9"

LIGHTS = {"FFFFFF", "B9CED6", "8FC3D2", "BBD3DB", "AFC0C7", "8FA9B5", "DCE5EA"}

# E 版页号（1-based，含 E 版页序）→ 官方章节名；p2 目录与 p17 致谢不保留
SECTION = {3: "病历简介", 4: "术前影像", 5: "术前准备", 6: "术前准备",
           7: "术前讨论一", 8: "术前讨论二", 9: "术中操作", 10: "术中影像",
           11: "术后情况", 12: "术后情况", 13: "术后情况", 14: "术后情况",
           15: "中长期随访", 16: "总结"}
KEEP_LINES = {5, 11}      # 化验/对比表保留浅灰行线
DROP_SUBTITLE = {16}      # 总结页标题即章节名，无需导语
# 个别页面正文与标签贴得太近，额外下移（按正文首词匹配）
NUDGE = {3: [("跌伤当日", 0.14), ("当日中午", 0.14), ("次日凌晨", 0.14), ("急诊手术", 0.14),
              ("女，6 月 8 天", 0.08), ("浅昏迷，GCS", 0.08), ("既往体健", 0.08)],
         9: [("插管全麻", 0.12), ("右侧颞顶入路", 0.12), ("磨钻钻孔", 0.12)],
         12: [("术前右瞳", 0.12), ("浅昏迷", 0.12), ("左上肢", 0.12)],
         14: [("双侧枕区", 0.15), ("睡眠周期", 0.15), ("醒睡各期", 0.15),
              ("监测期间", 0.15), ("正常范围", 0.15), ("背景活动", 0.08),
              ("睡眠期", 0.08), ("异常波", 0.08), ("发作期", 0.08), ("印象", 0.08)]}


def rgb(s):
    return RGBColor.from_string(s.lstrip("#"))


def run_color(r):
    try:
        if r.font.color is not None and r.font.color.type is not None:
            return str(r.font.color.rgb)
    except Exception:
        pass
    return None


def map_color(cur, size, big):
    if cur is None:
        return BODY
    cu = cur.upper()
    if cu == "B42318":
        return RED
    if cu == "0F7A4F":
        return GREEN
    if cu in ("0F6E6A", "0E5A78"):
        return ACC
    if cu in ("33424B", "0A1A23", "7C8B94"):
        return RGBColor.from_string(cu)
    if cu in LIGHTS:
        return TEAL if (big or (size or 0) >= 24) else BODY
    return RGBColor.from_string(cu)


def clear_slides(prs):
    lst = prs.slides._sldIdLst
    for sid in list(lst):
        try:
            prs.part.drop_rel(sid.get(qn("r:id")))
        except Exception:
            pass
        lst.remove(sid)


def blank_layout(prs):
    for lay in prs.slide_masters[0].slide_layouts:
        if lay.name in ("空白", "Blank"):
            return lay
    return prs.slide_masters[0].slide_layouts[-1]


def add_text(s, x, y, w, h, paras, align=None, anchor=MSO_ANCHOR.TOP):
    b = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = b.text_frame
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.vertical_anchor = anchor
    for m in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(tf, m, 0)
    first = True
    for p in paras:
        np = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        np.alignment = p.get("align") or align or PP_ALIGN.LEFT
        if p.get("spacing"):
            np.line_spacing = p["spacing"]
        for r in p["runs"]:
            nr = np.add_run()
            nr.text = r["text"]
            nr.font.name = FONT
            nr.font.size = Pt(r["size"])
            nr.font.bold = bool(r.get("bold"))
            nr.font.color.rgb = r["color"]
            if r.get("spc"):
                nr._r.get_or_add_rPr().set("spc", str(r["spc"]))
    return b


def add_line(s, x1, y1, x2, y2):
    conn = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1),
                                  Inches(x2), Inches(y2))
    conn.line.color.rgb = rgb(HAIR)
    conn.line.width = Pt(0.75)
    el = conn._element
    for ch in list(el):
        if ch.tag.endswith("}style"):
            el.remove(ch)


def extract_paras(sh, page_idx, big):
    """把 E 版文本框转成素颜段落描述；白/浅色文字按字号映射为深色。"""
    out = []
    tf = sh.text_frame
    for p in tf.paragraphs:
        runs = []
        for r in p.runs:
            if not r.text:
                continue
            size = r.font.size.pt if r.font.size else 14
            cur = run_color(r)
            runs.append({"text": r.text, "size": size, "color": map_color(cur, size, big),
                         "bold": bool(r.font.bold), "spc": (r._r.find(qn("a:rPr")).get("spc")
                       if r._r.find(qn("a:rPr")) is not None else None)})
        if runs:
            out.append({"runs": runs, "align": p.alignment, "spacing": p.line_spacing})
    return out


def main():
    base = Presentation(BASE)
    content = Presentation(EDECK)
    tmp = []
    clear_slides(base)
    lay = blank_layout(base)
    es = list(content.slides)

    # ---- 封面（完全按官方模板封面版式：大赛名 32pt 顶部居中 + 成员内容区 + y=4.93 横线）----
    s = base.slides.add_slide(lay)
    comp = next(sh.text_frame.text.strip() for sh in es[0].shapes
                if sh.has_text_frame and "武威" in sh.text_frame.text)
    case = next(sh for sh in es[0].shapes if sh.has_text_frame and "月龄" in sh.text_frame.text)
    add_text(s, 0.33, 0.28, 13.00, 1.45,
             [{"runs": [{"text": comp, "size": 32, "color": TEAL, "bold": True}]}],
             align=PP_ALIGN.CENTER)
    cparas = extract_paras(case, 1, True)
    for p in cparas:
        p["align"] = PP_ALIGN.CENTER
        for r in p["runs"]:
            r["size"] = min(r["size"], 28)
            r["color"] = INK
            r["bold"] = True
    add_text(s, 1.71, 3.62, 10.00, 1.31, cparas, align=PP_ALIGN.CENTER)
    add_line(s, 1.71, 4.93, 11.87, 4.93)
    s.notes_slide.notes_text_frame.text = es[0].notes_slide.notes_text_frame.text.strip()

    # ---- 内容页（E 版页序 3..16；跳过 p2 目录、p17 致谢）----
    gpage = 1
    for page_idx in range(3, 17):
        gpage += 1
        eslide = es[page_idx - 1]
        s = base.slides.add_slide(lay)
        sec = SECTION[page_idx]

        # 1) 标题：官方章节名，40pt、y=0.15、居中（与官方模板标题框一致）
        add_text(s, 0.92, 0.15, 11.50, 1.00,
                 [{"runs": [{"text": sec, "size": 40, "color": TEAL, "bold": True}]}],
                 align=PP_ALIGN.CENTER)
        # 2) 导语：原 E 版页面标题句，作为正文区第一行（左对齐深色，模板正文样式）
        if page_idx not in DROP_SUBTITLE:
            sub = next((sh for sh in eslide.shapes if sh.has_text_frame and
                        is_page_title(eslide, sh)), None)
            if sub is not None and sub.text_frame.text.strip():
                sp = extract_paras(sub, page_idx, False)
                for p in sp:
                    p["align"] = PP_ALIGN.LEFT
                    for r in p["runs"]:
                        r["size"] = 18
                        r["color"] = INK
                        r["bold"] = True
                add_text(s, 0.64, 1.58, 11.50, 0.4, sp)

        # 3) 正文：纯文本迁移；图片/视频原位；装饰全部去掉
        #    顶部内容统一整体下移到导语线以下（保持相对间距，不互相叠压）
        CONTENT_TOP = 2.05
        items = []
        for sh in eslide.shapes:
            st = str(sh.shape_type)
            try:
                x, y = Emu(sh.left).inches, Emu(sh.top).inches
                w, h = Emu(sh.width).inches, Emu(sh.height).inches
            except Exception:
                continue
            items.append((st, sh, x, y, w, h))
        content_items = [it for it in items
                         if not (it[0].startswith("TEXT") and is_page_title(eslide, it[1])
                                 and it[4] > 6)]
        pageno = [it for it in content_items
                  if it[0].startswith("TEXT")
                  and re.fullmatch(r"\d{2}\s*/\s*\d+", it[1].text_frame.text.strip())]
        body_items = [it for it in content_items if it not in pageno]
        delta = 0.0
        if body_items:
            min_y = min(it[3] for it in body_items if it[3] > 1.0)
            delta = max(0.0, CONTENT_TOP - min_y)
            max_bot = max(it[3] + it[5] for it in body_items)
            if max_bot + delta > 7.34:
                delta = max(0.0, 7.34 - max_bot)

        nudges = NUDGE.get(page_idx, [])

        def nudge_of(sh):
            t = sh.text_frame.text.strip() if sh.has_text_frame else ""
            for pref, extra in nudges:
                if t.startswith(pref):
                    return extra
            return 0.0

        def adj(y, sh=None):
            y2 = y + delta
            if sh is not None:
                y2 += nudge_of(sh)
            return y2

        for st, sh, x, y, w, h in items:
            yy = adj(y)
            if st.startswith("TEXT"):
                if is_page_title(eslide, sh):
                    continue  # 已作导语
                if y < 1.3 and w > 6:
                    continue  # 顶部章节眉不迁
                if re.fullmatch(r"\d{2}\s*/\s*\d+", sh.text_frame.text.strip()):
                    continue  # 页码稍后统一补
                paras = extract_paras(sh, page_idx, False)
                if not paras:
                    continue
                add_text(s, x, max(adj(y, sh), CONTENT_TOP + nudge_of(sh)), w, h, paras)
            elif st.startswith("AUTO_SHAPE"):
                if sh.has_text_frame and sh.text_frame.text.strip():
                    paras = extract_paras(sh, page_idx, False)
                    add_text(s, x, max(adj(y, sh), CONTENT_TOP + nudge_of(sh)), w, h, paras)
                # 形状本身（色块/雪佛龙）不迁
            elif st.startswith("LINE"):
                if page_idx in KEEP_LINES:
                    add_line(s, x, y, x + w, y + h)
            elif st.startswith("PICTURE"):
                if w < 0.5 and h < 0.5:
                    continue
                s.shapes.add_picture(io.BytesIO(sh.image.blob), Inches(x), Inches(adj(y, sh)),
                                     Inches(w), Inches(h))
            elif st.startswith("MEDIA"):
                el = sh._element
                vid = el.find(".//" + qn("a:videoFile"))
                blob = None
                poster = None
                if vid is not None:
                    blob = eslide.part.rels[vid.get(qn("r:link"))].target_part.blob
                blip = el.find(".//" + qn("a:blip"))
                if blip is not None:
                    try:
                        poster = eslide.part.rels[blip.get(qn("r:embed"))].target_part.blob
                    except Exception:
                        poster = None
                vp = pp = None
                if blob:
                    f1 = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
                    f1.write(blob)
                    f1.close()
                    vp = f1.name
                    tmp.append(vp)
                if poster:
                    f2 = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                    f2.write(poster)
                    f2.close()
                    pp = f2.name
                    tmp.append(pp)
                try:
                    s.shapes.add_movie(vp, Inches(x), Inches(adj(y, sh)), Inches(w), Inches(h),
                                       poster_frame_image=pp, mime_type="video/mp4")
                except Exception as exc:
                    print(f"  WARN p{page_idx} 视频迁移失败: {exc}")

        if eslide.has_notes_slide:
            s.notes_slide.notes_text_frame.text = eslide.notes_slide.notes_text_frame.text.strip()

        add_text(s, 11.0, 7.06, 1.5, 0.24,
                 [{"runs": [{"text": f"{gpage:02d} / 15", "size": 12, "color": MUTED}]}],
                 align=PP_ALIGN.RIGHT)

    for f in tmp:
        try:
            os.unlink(f)
        except Exception:
            pass
    base.save(DST)
    print(f"built {DST} ({os.path.getsize(DST)/1048576:.1f} MB)  slides={len(base.slides.__iter__.__self__._sldIdLst)}")

    lint = os.path.expanduser("~/.local/deck-lint/deck_lint.py")
    rc = subprocess.run([sys.executable, lint, DST, "--min-notes", "300"]).returncode
    if rc:
        print("== RESULT: BUILD FAILED (deck-lint FAIL)")
        return 1
    print("== RESULT: BUILD OK")
    return 0


def is_page_title(eslide, sh):
    """E 版页面大标题：页面顶部(y<0.95)的 24pt+ 文本框。"""
    try:
        y = Emu(sh.top).inches
    except Exception:
        return False
    if y >= 0.95:
        return False
    for p in sh.text_frame.paragraphs:
        for r in p.runs:
            if r.font.size is not None and r.font.size.pt >= 24:
                return True
    return False


if __name__ == "__main__":
    sys.exit(main())
