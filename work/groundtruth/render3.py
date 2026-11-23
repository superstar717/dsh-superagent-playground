# -*- coding: utf-8 -*-
# 正叙极简版渲染：pass1 拼接(plan3) -> base3.mp4；pass2 轻量字幕 + 首尾淡入淡出 -> final3.mp4
# 无运镜/花字/whoosh（该版风格即"极简正叙"）；拼接防咔哒淡入淡出与 render2.py 同配方
import json, subprocess

WORK = "D:/video_edit_work"
plan = json.load(open(WORK + "/plan3.json", encoding="utf-8"))
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
         "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", WORK + "/base3.mp4"]
print("pass1 ...", flush=True)
run(args)

# ---- pass 2：轻量字幕 + 首尾淡入淡出 ----
args = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", WORK + "/base3.mp4",
        "-filter_complex",
        "[0:v]fade=t=in:st=0:d=0.25,fade=t=out:st=%.2f:d=0.45,ass=filename=final3.ass[v];"
        "[0:a]afade=t=out:st=%.2f:d=0.4[a]" % (DUR - 0.5, DUR - 0.45),
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", WORK + "/final3.mp4"]
print("pass2 ...", flush=True)
run(args, cwd=WORK)

# ---- 时长对账 + 抽检帧 ----
p = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1",
         WORK + "/final3.mp4"])
out_dur = float(p.stdout.strip())
print("output=%.2fs expected=%.2fs diff=%.2fs" % (out_dur, DUR, out_dur - DUR))
for name, t in (("f3_start", 1.5), ("f3_mid", 78.0), ("f3_end", out_dur - 1.2)):
    run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "%.1f" % t, "-i", WORK + "/final3.mp4",
         "-frames:v", "1", "%s/%s.png" % (WORK, name)])
    print("frame %s" % name)
print("RENDER3-OK" if abs(out_dur - DUR) < 0.5 else "DURATION-MISMATCH")
