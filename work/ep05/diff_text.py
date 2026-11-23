#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""whisper 词级文本 vs 定稿文案（知识库 §1，作者画面字幕还原）的序列对齐：
①验证 whisper 文本骨架完整（总长/覆盖）；②找出 whisper 的专名误识 → 谱 fixes 候选。
fixes 只修「写法」（专名/数字），不改断词；修什么以两张表的重叠证据为准。"""
import json, re, difflib

cor = re.sub(r"[\s，。、！？：；「」（）…·,.]", "", open("corrected_script.txt", encoding="utf-8").read())
tr = json.load(open("transcript_whisper.json", encoding="utf-8"))
wt = re.sub(r"[\s，。、！？：；「」（）…·,.]", "", "".join(w["word"] for s in tr["segments"] for w in s["words"]))
print("corrected=%d chars, whisper=%d chars, ratio=%.3f" % (len(cor), len(wt), len(wt) / len(cor)))

sm = difflib.SequenceMatcher(None, cor, wt, autojunk=False)
diffs = []
for op, i1, i2, j1, j2 in sm.get_opcodes():
    if op != "equal":
        diffs.append((op, cor[max(0,i1-8):i2+8], wt[max(0,j1-8):j2+8]))
print("non-equal blocks: %d" % len(diffs))
for op, a, b in diffs[:40]:
    print("  %-6s 定稿[…%s…] whisper[…%s…]" % (op, a, b))
json.dump({"ratio": len(wt)/len(cor), "blocks": len(diffs), "detail": diffs},
          open("diff_whisper_corrected.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
