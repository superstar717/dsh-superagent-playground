#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EP05 比对二：正向 beat 切分 vs 知识库 §5 模块表（独立参考标注，±1s 粒度）。
对每个模块找重叠最大的谱 beat，报告边界偏差与重叠率；另反向数谱 beat 落进哪个模块。"""
import json, sys

score = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "scores/ep05.score.json", encoding="utf-8"))
gt = json.load(open("groundtruth_author.json", encoding="utf-8"))
beats = score["beats"]
mods = gt["kb_modules"]

def ov(a1, a2, b1, b2):
    return max(0.0, min(a2, b2) - max(a1, b1))

rows, aligned = [], 0
for m in mods:
    best, best_o = None, 0.0
    for b in beats:
        o = ov(b["src"][0], b["src"][1], m["start"], m["end"])
        if o > best_o:
            best, best_o = b, o
    ma = m["end"] - m["start"]
    da = best["src"][0] - m["start"]
    db = best["src"][1] - m["end"]
    ok = abs(da) <= 4 and abs(db) <= 4
    aligned += ok
    rows.append({"module": m["name"], "kb": [m["start"], m["end"]], "beat": best["id"] + " " + best.get("role", ""),
                 "beat_src": best["src"], "overlap": round(best_o / ma, 2), "d_start": round(da, 1), "d_end": round(db, 1),
                 "aligned(±4s)": ok})

# beat→模块 反向映射（谱 beat 是否横跨多个模块）
span = []
for b in beats:
    hit = [m["name"] for m in mods if ov(b["src"][0], b["src"][1], m["start"], m["end"]) > 0.3 * (b["src"][1] - b["src"][0])]
    span.append({"beat": b["id"], "role": b.get("role"), "src": b["src"], "kb_modules": hit})

out = {"module_aligned": aligned, "modules_total": len(mods),
       "beat_single_module": sum(1 for s in span if len(s["kb_modules"]) == 1), "beats_total": len(beats),
       "rows": rows, "beat_to_modules": span}
json.dump(out, open("compare_beats_result.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for r in rows:
    print("%-14s kb=%s beat=%s ov=%.2f d=%+.1f/%+.1f %s" % (r["module"], r["kb"], r["beat"], r["overlap"], r["d_start"], r["d_end"], "OK" if r["aligned(±4s)"] else "DIFF"))
print("module aligned %d/%d; beats single-module %d/%d" % (aligned, len(mods), out["beat_single_module"], len(beats)))
