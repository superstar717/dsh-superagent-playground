# -*- coding: utf-8 -*-
"""F240ppt deck — E 版：以用户 2026-11-16 附件版（template_b.pptx，D 版团队手改稿）为基底的
"统一模板 + 放大字体 + 精简到 8 分钟"版本。

改动（对应用户 2026-11-16 飞书要求）：
  1. 结构按大赛统一模版：术前讨论两页（原倒数第 3、4 页）移入"术前准备"节；
     页码眉线、章节眉（PART 0x）与模版七节顺序对齐。
  2. 字体统一放大并统一层级（kicker 16 / 标题 32 / 正文 15–19 / 数据 22+，页码 12）。
  3. 内容精简：压缩文献墙、备注逐页重写至 ~1.3k 字（目标讲述 8 分钟）。

基底与授权：template_b.pptx 为用户在群内发送的当前工作版（其手改的临床细节一律保留，
只在"精简"授权范围内压缩冗词；3mm / 200ml / GCS 15 分等用户补录值进 cite-allow 注明）。

用法:
  python3 build_e.py                    # 交付版（微软雅黑）
  DECK_SUFFIX=-qa DECK_FONT="Heiti SC" python3 build_e.py   # QA 版另存
退出码: 0 成功（deck-lint 0 FAIL）/ 1 构建或 lint 失败。
"""
import os
import re
import subprocess
import sys

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.oxml.ns import qn

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.environ.get("TEMPLATE_B", os.path.join(HERE, "template_b.pptx"))
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)

FONT = os.environ.get("DECK_FONT", "微软雅黑")
SUFFIX = os.environ.get("DECK_SUFFIX", "")
NAME = "2026武威市神经外科诊疗技能大赛病例汇报-E版"
DST = os.path.join(OUT, f"{NAME}{SUFFIX}.pptx")

KICKER_COLOR = "8FC3D2"

# 字体放大映射（按现字号 → 新字号；保持层级，整体 ×1.25–1.35）
SIZE_MAP = {7.8: 11, 8.8: 11, 10: 12.5, 10.8: 12, 12: 15, 14: 17, 16: 19,
            20: 22, 24: 26, 28: 32, 31: 34, 32: 36, 36: 38, 38: 40}
# WPS 丢显式字号的占位 run（母版默认 18–20pt）：按同类元素显式补齐
NONE_SIZE = {
    (1, 5): 18,                                  # 封面眉
    (4, 8): 16, (4, 12): 16, (4, 16): 16,        # 影像要点小标
    (5, 42): 18, (5, 45): 18, (5, 48): 18,       # 右栏块标
    (6, 4): 20, (6, 7): 20, (6, 10): 20,         # 诊疗计划条目标
    (16, 4): 28, (16, 7): 28, (16, 10): 28,      # 总结序号
    (16, 6): 18, (16, 9): 18, (16, 12): 18,      # 总结正文
}
# 个别覆盖（auto map 之后）
SIZE_OVERRIDE = {
    (13, 6): 18, (13, 10): 18, (13, 14): 18,     # 随访三栏图注（16→19 太挤，定 18）
    (4, 9): 15, (4, 13): 15, (4, 17): 15,        # 影像要点正文（17 装不下，降 15）
    (6, 3): 28, (6, 6): 28, (6, 9): 28,          # 序号大数字：32 在窄框内竖排折行，回 28
    (7, 3): 28, (7, 7): 28, (7, 11): 28,
    (7, 5): 18, (7, 9): 18, (7, 13): 18,         # 术中三栏正文（19 挤到“手术节律”）
    (7, 15): 16, (7, 16): 16, (7, 17): 16, (7, 18): 16, (7, 19): 16,  # 雪佛龙条
}
# 行距收紧（放大后防溢出）
LINE_SPACING = {
    (4, 9): 1.2, (4, 13): 1.2, (4, 17): 1.2,
    (6, 15): 1.2, (6, 17): 1.15,
    (7, 5): 1.35, (7, 9): 1.35, (7, 13): 1.35,
    (10, 6): 1.3, (10, 8): 1.3,
    (12, 3): 1.3, (12, 5): 1.3,
    (14, 4): 1.25, (14, 7): 1.25, (14, 10): 1.25, (14, 13): 1.25,
    (14, 16): 1.25, (14, 19): 1.25,
    (15, 4): 1.25, (15, 6): 1.25, (15, 7): 1.25,
    (15, 11): 1.2, (15, 13): 1.2,
}

# ---- 文本精简/订正（保留用户全部临床事实，只压缩冗词、修笔误、统一标点）----
TEXT = {
    (2, 11): "化验解读、诊疗计划与术前讨论",
    (2, 23): "三点体会",
    (3, 16): "女，6 月 8 天。床上摔下致伤，“外伤后意识不清 1 天”入院。",
    (3, 18): "浅昏迷，GCS 7 分；前囟饱满、张力高；右瞳 6 mm 对光消失，左瞳 2 mm 灵敏。",
    (5, 49): "婴儿总血量约 80–85 ml/kg，血容量小、血肿 80 ml、已有休克表现，术前须备血、术中仔细止血，预防失血性休克。",
    (6, 5): "插管全麻下行右侧颞顶硬膜外血肿清除术；骨瓣是否还纳依术中情况决定。",
    (6, 8): "高年资麻醉医师全程监护，按体重估算导管型号；备小儿骨瓣固定方式；与家属充分沟通并签知情同意。",
    (6, 11): "血容量少、血肿量大、重度贫血伴低纤维蛋白原——循环与凝血是全程主线。",
    (6, 15): "共识：硬膜外血肿厚度 >10 mm 建议手术清除；儿童指征可适当放宽，神经功能恶化即可手术。",
    (6, 17): "手术目的：解除占位效应，为控制颅压与脑灌注创造条件。",
    (7, 5): "气管插管全麻；导管内径 d(mm)=W/2+2，深度 h(cm)=W+6；高年资麻醉医师全程监护。",
    (7, 13): "磨钻钻孔减少缺损；骨瓣预留活动空间，7 号双线漂浮固定，不用成人固定系统；头皮缝合不宜过紧。",
    (7, 20): "术中配合：开颅同时纠正贫血与凝血——自体血回输 + 悬浮红细胞 / 新鲜冰冻血浆，维持循环稳定。",
    (9, 4): "    舒芬太尼 0.5–2 μg/kg/h、咪达唑仑 60 μg/kg/h 泵入镇静镇痛；密切观察意识、瞳孔与肢体活动。",
    (9, 7): "    头孢呋辛静滴（按体重给药）；监测体温、血常规与切口愈合，警惕感染。",
    (9, 10): "    苯巴比妥钠肌注预防早期癫痫（按体重给药）；2 天后左乙拉西坦口服液序贯。",
    (9, 12): "    CPAP 辅助通气（FiO₂ 40%，SpO₂ 96%）；术后 10 h SBT 通过后拔管；维持 CPP 40–50 mmHg。",
    (10, 2): "术后瞳孔回缩、意识改善，复查 CT 未见迟发血肿",
    (10, 4): "术前右瞳 6 mm、对光消失 → 术后回缩至约 4 mm；\n次日双瞳约 3 mm、对光灵敏。",
    (10, 6): "浅昏迷逐渐恢复，呼之有反应；\n术后 24 小时 GCS 15 分。",
    (10, 8): "左上肢肌力约 3 级，其余肢体\n肌力正常，活动可",
    (11, 44): "术中/后予血浆 200 ml、术后人纤维蛋白原 0.5 g；FIB 0.61 → 2.52 g/L，可脱离血浆支持。",
    (12, 2): "术后 3 日 MRI 见右枕顶叶脑梗死；1 周脑电正常",
    (12, 3): "考虑外伤性脑梗死，与减压后灌注改变相关。",
    (12, 5): "甲钴胺营养神经；继续影像与神经功能随访。",
    (13, 6): "喂养反应改善，左侧肢体已恢复，右侧轻度面瘫减轻",
    (13, 10): "CT 三维重建：骨瓣对位愈合良好，软化灶形成",
    (13, 14): "爬行、扶站，行走可，运动良好，无后遗症（居家视频）",
    (14, 1): "术前讨论一：婴幼儿硬膜外血肿特点",
    (14, 4): "皮质抑制功能不完善，意识障碍出现早、与脑损伤程度不符；婴幼儿以哭闹、激惹、嗜睡起病，进行性加深；年长儿可见“昏迷—清醒—再昏迷”。",
    (14, 7): "颅压代偿能力强，增高表现出现晚，可仅见精神弱、嗜睡或躁动，晚期才见呕吐、前囟饱满。",
    (14, 13): "血肿压迫皮质可致对侧肢体无力；小儿皮质抑制功能不完善，伤后易发癫痫。",
    (14, 19): "婴幼儿活动多、危险意识差，颅脑损伤以坠落伤为主；0–2 岁警惕施加性损伤（约 5.9%）。",
    (15, 1): "术前讨论二：两类并发症的识别与防治",
    (15, 3): "    伤后 1–2 周内多见：脑血管发育不完全、低灌注与血管痉挛。",
    (15, 4): "    与原发伤无关的失语、偏瘫等应及时 CT/MRI；轻症钙拮抗剂、神经营养与扩容，严重者去骨瓣减压。儿童侧支循环建立快，预后好于成人。",
    (15, 6): "    婴幼儿皮质功能不稳定、兴奋易扩散：初期四肢痉挛性抽搐，后多转为局灶性发作。",
    (15, 11): "颅内压增高用高渗盐水或甘露醇降颅压：3% 高渗盐水 2–5 ml/kg、10–20 min。",
    (15, 13): "神经功能恶化、脑疝且常规降颅压无效者行去骨瓣减压，早期 <24 h 更有效；儿童颅骨成形无年龄限制。",
    (16, 6): "    婴幼儿表现不典型，嗜睡、易激惹、呕吐或一侧肌力减弱即应查 CT；本例血肿约 80 ml 伴脑疝，急诊减压是转归关键。",
    (16, 12): "    磨钻减缺损、漂浮骨板、头皮缝合不过紧；规范抗癫痫与呼吸管理，随访 1 年半发育良好。",
}

# ---- 删除孤立装饰（用户版删了配套文字后残留的小图标）----
REMOVE = [(11, 51), (13, 15), (14, 20)]

# ---- 备注逐页重写（目标 ~1.3k 字 ≈ 8 分钟讲述）----
NOTES = {
    1: "各位评委老师好。我汇报的病例是一例 6 月 8 天女婴，急性硬膜外血肿、脑疝形成，合并重度贫血与低纤维蛋白原血症。下面按术前评估、术前讨论、急诊手术、术后管理与随访来汇报。",
    2: "汇报分七个部分：病历简介、术前影像、术前准备（含术前讨论）、术中操作、术后情况、中长期随访和总结。",
    3: "患儿床上跌伤，初期哭闹如常，次日嗜睡，今晨呼之不应。查体浅昏迷，GCS 7 分，右瞳 6 mm 散大、对光消失，左瞳 2 mm 灵敏。诊断右侧颞顶硬膜外血肿、脑疝形成，急诊收住。",
    4: "急诊 CT：右顶硬膜外血肿约 80 ml，中线左移，脑疝形成；右顶叶密度降低，右顶骨可疑骨折。占位效应明确、神经功能恶化，具备急诊手术指征。",
    5: "术前化验：重度小细胞低色素性贫血，HGB 50；PT、TT 延长，纤维蛋白原仅 0.61。婴儿血容量小、血肿 80 ml 且已有休克表现，术前备血，术中自体血回输，备新鲜冰冻血浆。",
    6: "诊疗计划：急诊插管全麻行血肿清除术，骨瓣还纳与否术中决定。共识建议硬膜外血肿厚度超过 10 mm 即手术，儿童指征可适当放宽；围手术期同步纠正贫血与凝血。",
    7: "术前讨论一：婴幼儿硬膜外血肿特点。一是意识障碍不典型，本例初起仅哭闹、次日才嗜睡；二是颅压增高出现晚；三是瞳孔改变一旦出现往往已是脑疝，应尽早 CT；致伤以坠落为主，0 到 2 岁警惕施加性损伤。",
    8: "术前讨论二：两类并发症。外伤性脑梗死多在伤后 1 到 2 周内，出现与原发伤不符的失语、偏瘫要及时复查影像，治疗按轻重症分级处理，儿童侧支循环建立快、预后好于成人；创伤后癫痫持续脑电有助于识别，预防用药可减少早期发作。",
    9: "手术在插管全麻下进行：右侧颞顶入路，牵开骨瓣、暴露硬膜，清除硬膜外血肿并彻底止血。磨钻钻孔减少缺损，骨瓣预留活动空间、7 号双线漂浮固定，头皮缝合不宜过紧。",
    10: "这是术中八帧影像：从插管、体位、切口、去骨瓣到血肿清除、硬脑膜修补、漂浮骨瓣固定的全过程。",
    11: "术后管理四方面：舒芬太尼、咪达唑仑镇静镇痛；头孢呋辛抗感染；苯巴比妥后改左乙拉西坦预防癫痫；CPAP 辅助通气，10 小时后通过自主呼吸试验拔管，维持脑灌注。",
    12: "转归：术后右瞳回缩至约 4 mm，次日双瞳约 3 mm、对光灵敏，24 小时 GCS 15 分；6 小时、24 小时复查 CT 未见迟发血肿，减压充分，转出监护。",
    13: "术后 20 小时复查：HGB 从 50 回到 120，FIB 从 0.61 升到 2.52，输血与血浆支持有效；D-二聚体升高、AT-Ⅲ降低提示凝血激活，继续动态复查。",
    14: "术后 3 日 MRI 提示右枕顶叶脑梗死，考虑减压后灌注改变所致，予甲钴胺营养神经；术后 1 周脑电图正常，未见痫样放电，继续影像与神经功能随访。",
    15: "随访 1 年半：术后 20 天喂养与反应改善；1 年 CT 示骨瓣对位愈合；1 年半爬行、扶站、行走良好，无后遗症遗留。",
    16: "总结三点：第一，婴幼儿血肿表现不典型，急诊减压是转归关键；第二，围手术期容量与凝血管理贯穿全程；第三，个体化骨瓣处理配合规范术后管理与长期随访，患儿恢复良好。",
    17: "汇报完毕，感谢各位专家评委老师的聆听与指导。",
}

# ---- 版面修正（放大后防溢出/重叠；inch）----
GEO = {
    (1, 5): {"h": 0.34},
    # S03 三栏信息体加高
    (3, 16): {"h": 1.10}, (3, 18): {"h": 1.10}, (3, 20): {"h": 1.10},
    # S04 影像要点正文加高
    (4, 9): {"h": 0.56}, (4, 13): {"h": 0.56}, (4, 17): {"h": 0.56},
    # S05 右栏风险正文加高
    (5, 49): {"h": 0.95},
    # S06 序号框加宽防折行；正文加高；右栏第二块文字上移
    (6, 3): {"w": 0.54}, (6, 6): {"w": 0.54}, (6, 9): {"w": 0.54},
    (6, 8): {"h": 1.15}, (6, 11): {"h": 1.00},
    (6, 17): {"y": 3.12},
    # S07 序号框加宽；雪佛龙行下移让开三栏正文
    (7, 3): {"w": 0.54}, (7, 7): {"w": 0.54}, (7, 11): {"w": 0.54},
    # S10 左栏三块重排
    (10, 4): {"h": 1.30},
    (10, 5): {"y": 3.14},
    (10, 6): {"y": 3.52, "h": 0.70},
    (10, 7): {"y": 4.34},
    (10, 8): {"y": 4.70, "h": 0.95},
    # S11 化验表：术前列加宽防“×10¹²/L”折行，右列右移；D-二聚体两行，下方行距顺延
    (11, 4): {"w": 1.68},
    (11, 5): {"x": 3.60, "w": 2.50},
    (11, 30): {"y": 4.92}, (11, 31): {"y": 5.02}, (11, 32): {"y": 5.02},
    (11, 33): {"y": 5.02}, (11, 34): {"y": 5.42}, (11, 35): {"y": 5.52},
    (11, 36): {"y": 5.52}, (11, 37): {"y": 5.52}, (11, 38): {"y": 5.94},
    # S12 脑电图表整表下移加行距；治疗块上收
    (12, 4): {"y": 5.28}, (12, 5): {"y": 5.62, "h": 0.50},
    (12, 7): {"y": 1.74}, (12, 8): {"y": 1.66, "h": 0.62}, (12, 9): {"y": 2.44},
    (12, 10): {"y": 2.62}, (12, 11): {"y": 2.54, "h": 0.62}, (12, 12): {"y": 3.32},
    (12, 13): {"y": 3.50}, (12, 14): {"y": 3.42, "h": 0.42}, (12, 15): {"y": 4.20},
    (12, 16): {"y": 4.38}, (12, 17): {"y": 4.30, "h": 0.42}, (12, 18): {"y": 5.08},
    (12, 19): {"y": 5.26}, (12, 20): {"y": 5.18, "h": 0.62}, (12, 21): {"y": 5.96},
    (12, 22): {"y": 1.66, "h": 4.35},
    # S13 三栏图注收紧（避免压页码）
    (13, 6): {"h": 0.72}, (13, 10): {"h": 0.72}, (13, 14): {"h": 0.72},
    # S16 总结正文加高
    (16, 6): {"h": 0.75}, (16, 9): {"h": 0.75}, (16, 12): {"h": 0.75},
    # S14 讨论块加高（12→15 后两行内容可能到三行）
    (14, 4): {"h": 1.45}, (14, 7): {"h": 1.45}, (14, 10): {"h": 1.45},
    (14, 13): {"h": 1.45}, (14, 16): {"h": 1.45}, (14, 19): {"h": 1.45},
}
# 术中影像 8 图注条：原 0.32 加高到 0.44，文字框同步（S08/4,7,10,13,16,19,22,25 为条，+1 为字）
for _bar in (4, 7, 10, 13, 16, 19, 22, 25):
    GEO[(8, _bar)] = {"h": 0.44}
    GEO[(8, _bar + 1)] = {"h": 0.38}
# S11 术前值列统一加宽、术后值列统一右移
for _r in (8, 12, 16, 20, 24, 28, 32, 36):
    GEO[(11, _r)] = {"w": 1.68}
for _r in (9, 13, 17, 21, 25, 29, 33, 37):
    GEO[(11, _r)] = {"x": 3.60, "w": 2.50}

# ---- 页序：讨论两页（原 14、15）移入术前（原 6 之后）----
ORDER = [1, 2, 3, 4, 5, 6, 14, 15, 7, 8, 9, 10, 11, 12, 13, 16, 17]


def set_text(sh, new_text):
    """按段落重写文本；每段沿用基底首个 run 的字体属性。"""
    import copy

    tf = sh.text_frame
    txBody = tf._txBody
    lines = new_text.split("\n")
    proto_rPr = None
    for p in tf.paragraphs:
        for r in p.runs:
            el = r._r.find(qn("a:rPr"))
            if el is not None:
                proto_rPr = copy.deepcopy(el)
            break
        if proto_rPr is not None:
            break
    while len(tf.paragraphs) < len(lines):
        last = tf.paragraphs[-1]._p
        clone = copy.deepcopy(last)
        for r in clone.findall(qn("a:r")):
            clone.remove(r)
        txBody.append(clone)
    while len(tf.paragraphs) > len(lines):
        txBody.remove(tf.paragraphs[-1]._p)
    for i, p in enumerate(tf.paragraphs):
        for r in list(p.runs):
            r._r.getparent().remove(r._r)
        r = p.add_run()
        r.text = lines[i]
        if proto_rPr is not None:
            r._r.insert(0, copy.deepcopy(proto_rPr))
        r.font.name = FONT


def get_size(r):
    return r.font.size.pt if r.font.size else None


def main():
    prs = Presentation(SRC)
    slides = list(prs.slides)

    # 1. 文本重写（先于字号，避免 run 结构变化）
    for (si, shi), text in TEXT.items():
        set_text(slides[si - 1].shapes[shi], text)

    # 1b. 删除孤立装饰
    for si, shi in REMOVE:
        sh = slides[si - 1].shapes[shi]
        sh._element.getparent().remove(sh._element)

    # 2. 术前讨论两页补章节眉（与各页 kicker 同款式样）
    for si in (14, 15):
        s = slides[si - 1]
        b = s.shapes.add_textbox(Inches(0.85), Inches(0.14), Inches(9.0), Inches(0.32))
        tf = b.text_frame
        tf.word_wrap = True
        for m in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
            setattr(tf, m, 0)
        p = tf.paragraphs[0]
        r = p.add_run()
        r.text = "PART 03　术前准备"
        r.font.size = Pt(16)
        r.font.bold = True
        r.font.name = FONT
        r.font.color.rgb = RGBColor.from_string(KICKER_COLOR)
        r._r.get_or_add_rPr().set("spc", "240")

    # 3. 字号统一放大 + 覆盖
    for idx, s in enumerate(slides, 1):
        for sh in s.shapes:
            if not sh.has_text_frame:
                continue
            for p in sh.text_frame.paragraphs:
                for r in p.runs:
                    sz = get_size(r)
                    if sz is not None:
                        r.font.size = Pt(SIZE_MAP.get(sz, sz))
    for (si, shi), pt in NONE_SIZE.items():
        sh = slides[si - 1].shapes[shi]
        for p in sh.text_frame.paragraphs:
            for r in p.runs:
                if get_size(r) is None:
                    r.font.size = Pt(pt)
    for (si, shi), pt in SIZE_OVERRIDE.items():
        sh = slides[si - 1].shapes[shi]
        for p in sh.text_frame.paragraphs:
            for r in p.runs:
                r.font.size = Pt(pt)
    # 页码统一 12pt；章节眉统一 16pt
    for idx, s in enumerate(slides, 1):
        for sh in s.shapes:
            if not sh.has_text_frame:
                continue
            t = sh.text_frame.text.strip()
            if re.fullmatch(r"\d{2}\s*/\s*17", t):
                for p in sh.text_frame.paragraphs:
                    for r in p.runs:
                        r.font.size = Pt(12)
            elif t.startswith("PART ") or t.startswith("CASE") or t == "THANKS":
                for p in sh.text_frame.paragraphs:
                    for r in p.runs:
                        if r.font.size is None or r.font.size.pt < 18:
                            r.font.size = Pt(16)

    # 4. 行距与版面修正
    for (si, shi), ls in LINE_SPACING.items():
        sh = slides[si - 1].shapes[shi]
        for p in sh.text_frame.paragraphs:
            p.line_spacing = ls
    for (si, shi), attrs in GEO.items():
        sh = slides[si - 1].shapes[shi]
        if "x" in attrs:
            sh.left = Inches(attrs["x"])
        if "y" in attrs:
            sh.top = Inches(attrs["y"])
        if "w" in attrs:
            sh.width = Inches(attrs["w"])
        if "h" in attrs:
            sh.height = Inches(attrs["h"])

    # 5. 备注重写
    for i, s in enumerate(slides, 1):
        if i in NOTES:
            s.notes_slide.notes_text_frame.text = NOTES[i]

    # 6. 页序重排（讨论两页入术前）
    sldIdLst = prs.slides._sldIdLst
    ids = list(sldIdLst)
    for sid in ids:
        sldIdLst.remove(sid)
    for i in ORDER:
        sldIdLst.append(ids[i - 1])

    # 7. 页码文本同步（“14 / 17”等按新页序改写）
    for new_idx, s in enumerate(prs.slides, 1):
        for sh in s.shapes:
            if sh.has_text_frame:
                t = sh.text_frame.text.strip()
                m = re.fullmatch(r"(\d{2})\s*/\s*17", t)
                if m:
                    sh.text_frame.text = ""
                    p = sh.text_frame.paragraphs[0]
                    r = p.add_run()
                    r.text = f"{new_idx:02d} / 17"
                    r.font.size = Pt(12)
                    r.font.name = FONT

    prs.save(DST)
    size_mb = os.path.getsize(DST) / 1048576
    notes_total = sum(len(n) for n in NOTES.values())
    print(f"built {DST} ({size_mb:.1f} MB)  notes={notes_total} chars")

    # 8. 自跑 deck-lint
    lint = os.path.expanduser("~/.local/deck-lint/deck_lint.py")
    rc = subprocess.run([sys.executable, lint, DST, "--min-notes", "300"]).returncode
    if rc:
        print("== RESULT: BUILD FAILED (deck-lint FAIL)")
        return 1
    print("== RESULT: BUILD OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
