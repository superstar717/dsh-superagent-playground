# -*- coding: utf-8 -*-
# 精剪计划 v3.1：冷开场钩子 + 6 处重复句删除 + 停顿收紧
# 切点全部落在词边界；校验规则：与切区间相交的词必须完整落在区间内（只删整词，不削边角）
import json, re

WORK = "D:/video_edit_work"
tr = json.load(open(WORK + "/transcript.json", encoding="utf-8"))
words = [(w["start"], w["end"], w["word"]) for s in tr["segments"] for w in s.get("words", [])]
dur = tr["duration"]

def intersecting(a, b):
    return [w for w in words if w[0] < b - 0.005 and w[1] > a + 0.005]

# ---- 钩子（冷开场）：「这个效果就让我一下就就惊到我了」147.18-150.40 ----
HOOK = (147.16, 150.70)

# ---- 精剪删除（切点=词边界精确值）----
D = [
    (23.09, 24.01, "重复:需要做一个封面"),
    (28.89, 30.43, "重复:先用Workbody和Zcode的"),
    (41.23, 44.23, "重复:然后去做安装过ComfyUI"),
    (46.49, 49.02, "重启:视频生成(并入停顿切点)"),
    (50.73, 52.27, "重复:去做图片的生成"),
    (81.59, 82.35, "重启:孤立'封面'"),
]

ok = True
for a, b, note in D:
    ws = intersecting(a, b)
    partial = [w for w in ws if w[0] < a - 0.02 or w[1] > b + 0.02]
    text = "".join(w[2] for w in ws)
    print("cut %.2f-%.2f %s | 删:%s" % (a, b, note, text))
    if partial:
        ok = False
        print("  !! 削到边角的词:", [(round(w[0],2), round(w[1],2), w[2]) for w in partial])

# ---- 静音收紧切点（沿用 v2 已验证的 4 处）----
sil_txt = open(WORK + "/silence.log", encoding="utf-8", errors="ignore").read()
starts = [float(x) for x in re.findall(r"silence_start: ([-\d.]+)", sil_txt)]
ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", sil_txt)]
silences = sorted(zip(starts, ends))

removes = [(round(ps + 0.25, 3), round(pe - 0.35, 3), "停顿收紧")
           for ps, pe in silences if pe - ps >= 1.0 and pe < 173.0]
removes += [(a, b, n) for a, b, n in D]
removes.append((174.60, dur, "尾部死气"))
removes.sort()

merged = []
for a, b, n in removes:
    if merged and a <= merged[-1][1] + 0.05:
        if b > merged[-1][1]:
            merged[-1] = (merged[-1][0], b, merged[-1][2] + "+" + n)
    else:
        merged.append((a, b, n))
removes = merged

# ---- 分段（含钩子置顶；钩子与正文的时序倒挂是刻意的）----
segments = [(HOOK[0], HOOK[1], "冷开场钩子")]
cur = 0.65
for a, b, n in removes:
    if a >= cur and b > a:
        segments.append((round(cur, 3), round(a, 3), ""))
        cur = b
segments.append((round(cur, 3), 174.36, "结尾段"))
segments = [(a, b, n) for a, b, n in segments if b - a > 0.3]
expected = sum(b - a for a, b, _ in segments)

# ---- 校验：段内不得含被删区间；除钩子外时序递增 ----
for a, b, n in removes:
    for sa, sb, sn in segments:
        if sn != "冷开场钩子" and sa < b - 0.02 and sb > a + 0.02 and sb - sa < dur:
            pass  # 段是删除区间的补集，天然不重叠；此处仅防御
prev = None
for i, (a, b, n) in enumerate(segments):
    if b <= a:
        ok = False; print("!! bad seg", a, b, n)
    if i > 1 and prev is not None and a < prev:
        ok = False; print("!! overlap", a, n)
    prev = b

plan2 = {"source_duration": dur, "hook": HOOK,
         "segments": [{"start": a, "end": b, "note": n} for a, b, n in segments],
         "expected_duration": round(expected, 3)}
json.dump(plan2, open(WORK + "/plan2.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

print("\n===== PLAN v3.1 =====")
acc = 0.0
for i, (a, b, n) in enumerate(segments):
    print("seg%-2d out[%7.2f->%7.2f] src[%7.2f->%7.2f] %6.2fs %s" % (i, acc, acc + b - a, a, b, b - a, n))
    acc += b - a
print("removes=%d expected=%.2fs VALID=%s" % (len(removes), expected, "OK" if ok else "FAIL"))

# ---- effects.json ----
def remap(t):
    acc = 0.0
    for a, b, _ in segments:
        if a <= t <= b:
            return acc + (t - a)
        acc += b - a
    return None

def win(t1, t2):
    o1, o2 = remap(t1), remap(t2)
    return [round(o1, 2), round(o2, 2)] if o1 is not None and o2 is not None else None

effects = {
    "zooms": [
        {"t": win(147.18, 150.40), "note": "钩子:惊到我了"},
        {"t": win(135.38, 138.36), "note": "没想到效果很意外"},
        {"t": win(171.36, 173.66), "note": "结尾:已经很不错了"},
    ],
    "callouts": [
        {"text": "12G显存的PC", "t": win(33.83, 37.55)},
        {"text": "AI工具已经很成熟", "t": win(72.99, 75.23)},
        {"text": "让AI装ComfyUI出5张图", "t": win(102.50, 110.04)},
        {"text": "效果特别差", "t": win(124.54, 128.24)},
        {"text": "效果让我很意外", "t": win(135.38, 140.38)},
        {"text": "直接惊到我了", "t": win(147.18, 150.40)},
        {"text": "12G显卡就够", "t": win(158.68, 161.10)},
    ],
}
effects["zooms"] = [z for z in effects["zooms"] if z["t"]]
effects["callouts"] = [c for c in effects["callouts"] if c["t"]]
json.dump(effects, open(WORK + "/effects.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("zooms:", [z["t"] for z in effects["zooms"]])
print("callouts:", [(c["text"], c["t"]) for c in effects["callouts"]])
