# -*- coding: utf-8 -*-
# 正叙极简版计划 v3.2：去掉冷开场钩子，按源片时序正叙；保留 6 处重复句删除 + 4 处停顿收紧 + 尾部清理
# 校验规则与 build_plan2 相同：与切区间相交的词必须完整落在区间内（只删整词，不削边角）
import json, re

WORK = "D:/video_edit_work"
tr = json.load(open(WORK + "/transcript.json", encoding="utf-8"))
words = [(w["start"], w["end"], w["word"]) for s in tr["segments"] for w in s.get("words", [])]
dur = tr["duration"]

def intersecting(a, b):
    return [w for w in words if w[0] < b - 0.005 and w[1] > a + 0.005]

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
    print("cut %.2f-%.2f %s | del:%s" % (a, b, note, text))
    if partial:
        ok = False
        print("  !! partial word:", [(round(w[0], 2), round(w[1], 2), w[2]) for w in partial])

sil_txt = open(WORK + "/silence.log", encoding="utf-8", errors="ignore").read()
starts = [float(x) for x in re.findall(r"silence_start: ([-\d.]+)", sil_txt)]
ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", sil_txt)]
silences = sorted(zip(starts, ends))

removes = [(round(ps + 0.25, 3), round(pe - 0.35, 3), "pause-tighten")
           for ps, pe in silences if pe - ps >= 1.0 and pe < 173.0]
removes += [(a, b, n) for a, b, n in D]
removes.append((174.60, dur, "tail"))
removes.sort()

merged = []
for a, b, n in removes:
    if merged and a <= merged[-1][1] + 0.05:
        if b > merged[-1][1]:
            merged[-1] = (merged[-1][0], b, merged[-1][2] + "+" + n)
    else:
        merged.append((a, b, n))
removes = merged

# ---- 分段（正叙：无钩子置顶，纯时序补集）----
segments = []
cur = 0.65
for a, b, n in removes:
    if a >= cur and b > a:
        segments.append((round(cur, 3), round(a, 3), ""))
        cur = b
segments.append((round(cur, 3), 174.36, "ending"))
segments = [(a, b, n) for a, b, n in segments if b - a > 0.3]
expected = sum(b - a for a, b, _ in segments)

# ---- 校验：全段时序严格递增（无钩子，不允许任何例外）----
prev = None
for i, (a, b, n) in enumerate(segments):
    if b <= a:
        ok = False; print("!! bad seg", a, b, n)
    if prev is not None and a < prev:
        ok = False; print("!! overlap", a, n)
    prev = b

plan3 = {"source_duration": dur,
         "segments": [{"start": a, "end": b, "note": n} for a, b, n in segments],
         "expected_duration": round(expected, 3)}
json.dump(plan3, open(WORK + "/plan3.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

print("\n===== PLAN v3.2 chronological-minimal =====")
acc = 0.0
for i, (a, b, n) in enumerate(segments):
    print("seg%-2d out[%7.2f->%7.2f] src[%7.2f->%7.2f] %6.2fs" % (i, acc, acc + b - a, a, b, b - a))
    acc += b - a
print("removes=%d expected=%.2fs VALID=%s" % (len(removes), expected, "OK" if ok else "FAIL"))
