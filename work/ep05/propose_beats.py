#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EP05 正向产谱 · beat 边界候选推导（对词→beat 的机械部分）。
方法：从词级时间轴找篇章标记词（首先/然后/接下来/最后/到这里…）的句首位置，
输出候选边界时刻；beat 归并由人工/AI 按主题流定夺（决策层），本脚本不做归并。
所有时刻来自 ASR 词时间戳，不以 KB §5 模块表或作者字幕卡时间轴为输入。"""
import json, sys, re

tr = json.load(open("transcript_whisper.json", encoding="utf-8"))
words = [w for s in tr["segments"] for w in s["words"]]

MARKERS = ["首先", "然后", "正式开始", "你需要做", "这几个文件", "接下来", "这里拆完",
           "我审过", "各分段做好", "到这里", "最后单独", "最后如果", "这套SOP", "这套AI",
           "但是有一个东西", "第二是", "写每个分段", "很多人", "不过开场", "至于", "对我来",
           "文案我没啥经验", "生视频我用", "生视频的段落", "还有如果", "我还会先",
           "现在的流程", "我每期", "字幕主要", "至于音效", "人声、音效", "配音效"]

print("%8s  %s" % ("time", "marker context"))
for i, w in enumerate(words):
    t = w["word"]
    for m in MARKERS:
        if t.replace(" ", "").startswith(m) or m in t.replace(" ", "")[:6]:
            ctx = "".join(x["word"] for x in words[max(0, i - 2):i + 8])
            print("%8.2f  [%s] …%s…" % (w["start"], m, ctx[:34]))
            break

# 词间隙（>0.6s）也是天然停顿候选
print("\n--- word gaps > 0.6s ---")
for a, b in zip(words, words[1:]):
    gap = b["start"] - a["end"]
    if gap > 0.6:
        print("%7.2f-%7.2f (%.2fs)  %s | %s" % (a["end"], b["start"], gap, a["word"], b["word"]))
