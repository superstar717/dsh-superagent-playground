# -*- coding: utf-8 -*-
# 从 final.ass 生成 final.srt（剪映等工具可直接导入）
import re

WORK = "D:/video_edit_work"
txt = open(WORK + "/final.ass", encoding="utf-8").read()
ms = re.findall(r"Dialogue: 0,(\d+:\d+:[\d.]+),(\d+:\d+:[\d.]+),Default,,0,0,0,,(.+)", txt)

def sec(t):
    h, m, x = t.split(":")
    return int(h) * 3600 + int(m) * 60 + float(x)

def stmp(t):
    h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return "%02d:%02d:%06.3f" % (h, m, s)

with open(WORK + "/final.srt", "w", encoding="utf-8") as f:
    for i, (a, b, c) in enumerate(ms):
        f.write("%d\n%s --> %s\n%s\n\n" % (i + 1,
                stmp(sec(a)).replace(".", ","), stmp(sec(b)).replace(".", ","), c.strip()))
print("srt lines=%d" % len(ms))
