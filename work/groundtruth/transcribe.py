# -*- coding: utf-8 -*-
# 口播视频转写：faster-whisper, CUDA 优先 / CPU int8 兜底
import os, json, importlib.util, time

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

WORK = "D:/video_edit_work"
SRC = WORK + "/source.mp4"
OUT = WORK + "/transcript.json"


def find_nvidia_bin(sub):
    """在所有 site-packages 里定位 nvidia/<sub>/bin（pip wheel 的 DLL 目录）"""
    import site
    bases = []
    try:
        bases += site.getsitepackages()
    except Exception:
        pass
    bases.append(site.getusersitepackages())
    for base in bases:
        p = os.path.join(base, "nvidia", sub, "bin")
        if os.path.isdir(p):
            return p
    return None


added = []
for sub in ("cublas", "cudnn"):
    d = find_nvidia_bin(sub)
    if d:
        os.add_dll_directory(d)
        added.append(d)
print("DLL dirs:", added, flush=True)

from faster_whisper import WhisperModel

device, compute = "cuda", "float16"
try:
    model = WhisperModel("small", device=device, compute_type=compute, download_root=WORK + "/models")
    print("USING-GPU small/float16", flush=True)
except Exception as e:
    print("GPU failed:", repr(e), flush=True)
    device, compute = "cpu", "int8"
    model = WhisperModel("small", device=device, compute_type=compute, download_root=WORK + "/models")
    print("USING-CPU small/int8", flush=True)

t0 = time.time()
segments, info = model.transcribe(
    SRC, language="zh", word_timestamps=True, vad_filter=True,
    vad_parameters=dict(min_silence_duration_ms=300),
)
segs = []
for s in segments:
    words = [{"start": round(w.start, 3), "end": round(w.end, 3), "word": w.word} for w in (s.words or [])]
    segs.append({"start": round(s.start, 3), "end": round(s.end, 3), "text": s.text.strip(), "words": words})
dt = time.time() - t0

with open(OUT, "w", encoding="utf-8") as f:
    json.dump({"language": info.language, "duration": info.duration, "device": device,
               "transcribe_seconds": round(dt, 1), "segments": segs}, f, ensure_ascii=False, indent=1)

print("audio_duration=%.2fs transcribe_took=%.1fs device=%s segments=%d words=%d" % (
    info.duration, dt, device, len(segs), sum(len(s["words"]) for s in segs)), flush=True)
print("FIRST:", (segs[0]["text"][:80] if segs else "(none)"), flush=True)
print("LAST:", (segs[-1]["text"][:80] if segs else "(none)"), flush=True)
