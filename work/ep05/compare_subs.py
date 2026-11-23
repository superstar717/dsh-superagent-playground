#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EP05 比对一：正向生成的字幕行（执行器 ASS）vs 作者实际字幕卡（groundtruth_author.json）。
作者卡时间轴只在本脚本（比对阶段）使用，不进入产谱输入。
指标：卡匹配率（时刻±2s 内找到行 & 文本相似≥0.5 / ≥0.85）、行起点对卡起点的精度/召回、时刻偏差。"""
import json, re, difflib, sys

ass_path = sys.argv[1] if len(sys.argv) > 1 else "score.ass"
gt = json.load(open("groundtruth_author.json", encoding="utf-8"))

def norm(s):
    return re.sub(r"[\s，。、！？：；「」『』（）《》…·,.:;!?\"'()-]+", "", s)

lines = []
for ln in open(ass_path, encoding="utf-8"):
    m = re.match(r"Dialogue: \d+,(\d+:\d+:\d+\.\d+),(\d+:\d+:\d+\.\d+),Default,", ln)
    if not m:
        continue

    def sec(ts):
        h, mi, rest = ts.split(":")
        return int(h) * 3600 + int(mi) * 60 + float(rest)
    parts = ln.split(",", 9)
    lines.append({"start": sec(parts[1]), "end": sec(parts[2]), "text": parts[9].strip()})

cards = gt["cards"]
matched_05 = matched_085 = 0
offsets = []
unmatched = []
for c in cards:
    cn = norm(c["text"])
    best, best_score = None, 0.0
    for l in lines:
        if l["start"] > c["end"] + 2.0 or l["end"] < c["start"] - 2.0:
            continue
        if abs(l["start"] - c["start"]) > 2.0:
            continue
        sc = difflib.SequenceMatcher(None, cn, norm(l["text"])).ratio()
        if sc > best_score:
            best, best_score = l, sc
    if best and best_score >= 0.5:
        matched_05 += 1
        offsets.append(abs(best["start"] - c["start"]))
        if best_score >= 0.85:
            matched_085 += 1
    else:
        unmatched.append({"card": c["text"], "t": c["start"], "best": (best or {}).get("text", ""), "sim": round(best_score, 2)})

# 行起点 → 卡起点（行是否踩在作者卡边界上）；反之亦然
def near(a, bs, tol=1.5):
    return any(abs(a - b) <= tol for b in bs)
ls = [l["start"] for l in lines]
cs = [c["start"] for c in cards]
prec = sum(1 for x in ls if near(x, cs)) / max(len(ls), 1)
rec = sum(1 for x in cs if near(x, ls)) / max(len(cs), 1)

out = {
    "our_lines": len(lines), "author_cards": len(cards),
    "card_matched_sim>=0.5": matched_05, "card_matched_sim>=0.85": matched_085,
    "card_match_rate": round(matched_05 / len(cards), 3),
    "median_offset_s": round(sorted(offsets)[len(offsets) // 2], 2) if offsets else None,
    "line_start_precision(±1.5s)": round(prec, 3),
    "card_start_recall(±1.5s)": round(rec, 3),
    "unmatched_sample": unmatched[:12],
}
json.dump(out, open("compare_subs_result.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in out.items() if k != "unmatched_sample"}, ensure_ascii=False, indent=1))
print("unmatched(%d):" % len(unmatched))
for u in unmatched[:12]:
    print("  %6.1fs sim=%.2f 卡:%s | 行:%s" % (u["t"], u["sim"], u["card"][:22], u["best"][:22]))
