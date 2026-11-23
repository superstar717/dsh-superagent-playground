# -*- coding: utf-8 -*-
# 正叙极简版字幕：plan3 重映射 + 跨行词修复；无花字。样式：雅黑 31px 细边轻量
import json

WORK = "D:/video_edit_work"
plan = json.load(open(WORK + "/plan3.json", encoding="utf-8"))
tr = json.load(open(WORK + "/transcript.json", encoding="utf-8"))
segs = plan["segments"]

TOL = 0.08
def remap(t):
    acc = 0.0
    for s in segs:
        if s["start"] - TOL <= t <= s["end"] + TOL:
            return min(max(acc + (t - s["start"]), 0.0), acc + (s["end"] - s["start"]))
        acc += s["end"] - s["start"]
    return None

join_times = []
acc = 0.0
for i in range(len(segs) - 1):
    acc += segs[i]["end"] - segs[i]["start"]
    join_times.append(round(acc, 2))

FIXES = [("康佛UI", "ComfyUI"), ("CoffeeLine", "ComfyUI"), ("康佛 UI", "ComfyUI"),
         ("PCA机", "PC机"), ("PCA 机", "PC机"), ("瓶子机", "台式机"), ("这是库的", "知识库的"),
         ("关于这是库", "关于知识库")]
BOUNDARY_FWD = [("康佛", "UI"), ("Coff", "eeLine"), ("瓶", "子机")]

def fix_text(s):
    for a, b in FIXES:
        s = s.replace(a, b)
    return s

words = []
for seg in tr["segments"]:
    for w in seg.get("words", []):
        o_s, o_e = remap(w["start"]), remap(w["end"])
        if o_s is None or o_e is None:
            continue
        words.append((o_s, o_e, w["word"]))

lines, cur, cur_start, cur_end = [], [], None, None
MAXLEN, MAXGAP, MINDUR = 16, 0.7, 0.8
def crosses_join(a, b):
    return any(a < jt - 0.02 < b for jt in join_times)
for (s, e, w) in words:
    wclean = w.strip()
    if not wclean:
        continue
    if cur and (len("".join(cur)) + len(wclean) > MAXLEN or s - cur_end > MAXGAP or crosses_join(cur_end, s)):
        lines.append((cur_start, cur_end, "".join(cur)))
        cur, cur_start, cur_end = [], None, None
    if cur_start is None:
        cur_start = s
    cur.append(wclean)
    cur_end = e
if cur:
    lines.append((cur_start, cur_end, "".join(cur)))

# 跨行修复：行尾碎片并入下行行首；单字续行并回上行
fixed = [list(x) for x in lines]
i = 0
while i < len(fixed) - 1:
    a, b2 = fixed[i], fixed[i + 1]
    for frag, head in BOUNDARY_FWD:
        if a[2].endswith(frag) and b2[2].startswith(head):
            a[2] = a[2][:-len(frag)]
            b2[2] = frag + b2[2]
    if len(b2[2]) <= 1:
        a[2] += b2[2]
        a[1] = b2[1]
        fixed.pop(i + 1)
        i -= 1
    i += 1

out_lines = []
for s, e, t in fixed:
    t = fix_text(t).strip()
    if not t:
        continue
    if e - s < MINDUR:
        e = s + MINDUR
    out_lines.append([s, e, t])
for i in range(len(out_lines) - 1):
    if out_lines[i][1] > out_lines[i + 1][0] - 0.05:
        out_lines[i][1] = max(out_lines[i][0] + 0.4, out_lines[i + 1][0] - 0.05)

def ts(t):
    h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return "%d:%02d:%05.2f" % (h, m, s)

header = """[Script Info]
ScriptType: v4.00+
PlayResX: 544
PlayResY: 960
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Microsoft Ya Hei,31,&H00FFFFFF,&H00FFFFFF,&H00101010,&H00000000,0,0,0,0,100,100,0,0,1,1.2,0,2,10,10,216,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
body = ""
for s, e, t in out_lines:
    body += "Dialogue: 0,%s,%s,Default,,0,0,0,,%s\n" % (ts(s), ts(e), t)
open(WORK + "/final3.ass", "w", encoding="utf-8").write(header + body)
print("subs=%d joins=%s" % (len(out_lines), join_times))
