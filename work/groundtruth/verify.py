# -*- coding: utf-8 -*-
# QC：逐 join 提取前后帧 + 音频电平证据 + 首尾帧
import json, subprocess, os

WORK = "D:/video_edit_work"
QC = WORK + "/qc"
os.makedirs(QC, exist_ok=True)
plan = json.load(open(WORK + "/plan.json", encoding="utf-8"))
segs = plan["segments"]

# join 的输出时间 = 前面各段累计时长
joins = []
acc = 0.0
for i in range(len(segs) - 1):
    acc += segs[i]["end"] - segs[i]["start"]
    joins.append(round(acc, 2))
print("join output times:", joins)

def run(args):
    r = subprocess.run(args, capture_output=True, text=True)
    return r.returncode, (r.stderr or "")[-400:]

# 帧：每个 join 前后各 0.35s；首尾帧
frame_ts = []
for t in joins:
    frame_ts += [("join%.0f_before" % (t * 10), t - 0.35), ("join%.0f_after" % (t * 10), t + 0.35)]
frame_ts += [("head_first", 0.05), ("tail_last", 166.0)]

for name, t in frame_ts:
    rc, err = run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "%.2f" % max(t, 0),
                   "-i", WORK + "/compact.mp4", "-frames:v", "1", "%s/%s.png" % (QC, name)])
    print("frame %s rc=%d %s" % (name, rc, err.replace("\n", " ")))

# 音频：join 两侧各 0.35s 窗口 mean volume
for j, t in enumerate(joins):
    for side, a, b in (("pre", max(t - 0.35, 0), 0.35), ("post", t, 0.35)):
        rc, err = run(["ffmpeg", "-ss", "%.2f" % a, "-t", "%.2f" % b, "-i", WORK + "/compact.mp4",
                       "-vn", "-af", "volumedetect", "-f", "null", "-"])
        m = re_mean = None
        import re
        mm = re.search(r"mean_volume: ([-\d.]+) dB", err)
        mm2 = re.search(r"max_volume: ([-\d.]+) dB", err)
        print("join%d %s mean=%s max=%s" % (j, side, mm.group(1) if mm else "?", mm2.group(1) if mm2 else "?"))
print("QC-FILES-DONE")
