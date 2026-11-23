# -*- coding: utf-8 -*-
# 精剪渲染：pass1 拼接(防咔哒音频淡入淡出) -> base2.mp4
#            pass2 运镜 overlay + 花字字幕 + 首尾淡入淡出 + 切点 whoosh -> final2.mp4
import json, subprocess, os

WORK = "D:/video_edit_work"
plan = json.load(open(WORK + "/plan2.json", encoding="utf-8"))
fx = json.load(open(WORK + "/effects.json", encoding="utf-8"))
segs = plan["segments"]
DUR = plan["expected_duration"]

def run(args, **kw):
    r = subprocess.run(args, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        print("rc=%d" % r.returncode)
        print(r.stderr[-1800:])
        raise SystemExit(1)
    return r

# ---- pass 1：拼接（每段音频 8ms 边缘淡入淡出防咔哒）----
args = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
for s in segs:
    args += ["-ss", str(s["start"]), "-t", str(round(s["end"] - s["start"], 3)), "-i", WORK + "/source.mp4"]
n = len(segs)
fc = ""
for i in range(n):
    d = segs[i]["end"] - segs[i]["start"]
    fc += "[%d:a]afade=t=in:st=0:d=0.008,afade=t=out:st=%.3f:d=0.008[a%d];" % (i, max(d - 0.01, 0), i)
fc += "".join("[%d:v][a%d]" % (i, i) for i in range(n))
fc += "concat=n=%d:v=1:a=1[v][a]" % n
args += ["-filter_complex", fc, "-map", "[v]", "-map", "[a]",
         "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", WORK + "/base2.mp4"]
print("pass1 ...", flush=True)
run(args)

# ---- whoosh 音效素材（0.5s 柔和气声）----
run(["ffmpeg", "-y", "-loglevel", "error",
     "-f", "lavfi", "-i", "anoisesrc=d=0.5:c=brown:a=0.9",
     "-af", "lowpass=f=900,highpass=f=180,afade=t=in:st=0:d=0.18,afade=t=out:st=0.22:d=0.28,volume=0.5",
     WORK + "/whoosh.wav"])

# ---- join 输出时刻（含钩子后第一 join；选 3 个大转场 + 钩子接点）----
joins = []
acc = 0.0
for i in range(len(segs) - 1):
    acc += segs[i]["end"] - segs[i]["start"]
    joins.append(round(acc, 2))
whoosh_joins = [joins[0], 106.93, 131.85]  # 钩子->正片 / 人脸->屏幕 / 第一张->第二张
whoosh_joins = [t for t in whoosh_joins if t < DUR - 1]

# ---- pass 2：运镜 + 字幕花字 + 淡入淡出 + 音效 ----
n_in = 1 + len(whoosh_joins)
args = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", WORK + "/base2.mp4"]
for _ in whoosh_joins:
    args += ["-i", WORK + "/whoosh.wav"]

cw, ch = 508, 898  # 1.07x 中心裁切（偶数）
z = "crop=%d:%d:%d:%d,scale=544:960,setsar=1" % (cw, ch, (544 - cw) // 2, (960 - ch) // 2)
splits = "".join("[z%d]" % i for i in range(len(fx["zooms"])))
fc = "[0:v]split=%d[base]%s;" % (1 + len(fx["zooms"]), splits)
for i, zm in enumerate(fx["zooms"]):
    fc += "[z%d]%s[zz%d];" % (i, z, i)
prev = "base"
for i, zm in enumerate(fx["zooms"]):
    outl = "o%d" % i if i < len(fx["zooms"]) - 1 else "oz"
    fc += "[%s][zz%d]overlay=enable='between(t,%.2f,%.2f)'[%s];" % (prev, i, zm["t"][0], zm["t"][1], outl)
    prev = outl
fc += "[%s]fade=t=in:st=0:d=0.25,fade=t=out:st=%.2f:d=0.45,ass=filename=final2.ass[v];" % (prev, DUR - 0.5)
a_in = "[0:a]"
for i, t in enumerate(whoosh_joins):
    fc += "[%d:a]adelay=%d:all=1[w%d];" % (1 + i, int(t * 1000) - 150, i)
    a_in += "[w%d]" % i
fc += "%samix=inputs=%d:normalize=0,afade=t=out:st=%.2f:d=0.4[a]" % (a_in, 1 + len(whoosh_joins), DUR - 0.45)

args += ["-filter_complex", fc, "-map", "[v]", "-map", "[a]",
         "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", WORK + "/final2.mp4"]
print("pass2 ...", flush=True)
run(args, cwd=WORK)

# ---- 时长对账 + 抽检帧 ----
p = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1",
         WORK + "/final2.mp4"], )
out_dur = float(p.stdout.strip())
print("output=%.2fs expected=%.2fs diff=%.2fs" % (out_dur, DUR, out_dur - DUR))

for name, t in (("f2_hook", 1.6), ("f2_callout", 35.5), ("f2_zoom", 126.8),
                ("f2_callout2", 116.0), ("f2_end", 159.8)):
    run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "%.1f" % t, "-i", WORK + "/final2.mp4",
         "-frames:v", "1", "%s/%s.png" % (WORK, name)])
    print("frame %s" % name)
print("RENDER2-OK" if abs(out_dur - DUR) < 0.5 else "DURATION-MISMATCH")
