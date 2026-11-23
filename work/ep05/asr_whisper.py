#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EP05 正向产谱 · 第一步「对词」：faster-whisper 词级时间戳 → transcript.json
输出格式与剪辑谱执行器契约一致：{"duration": s, "segments": [{"start","end","text","words":[{"start","end","word"}]}]}
词时间戳来自声学对齐（不是插值）；文本层量另与 SenseVoice 已知文本交叉核对（另一步）。
"""
import json, sys, time
from faster_whisper import WhisperModel

AUDIO = "media/ajfda_16k.wav"
OUT = "transcript_whisper.json"

t0 = time.time()
model = WhisperModel("medium", device="cpu", compute_type="int8", cpu_threads=6)
segments, info = model.transcribe(AUDIO, language="zh", word_timestamps=True,
                                  vad_filter=True, vad_parameters={"min_silence_duration_ms": 400},
                                  condition_on_previous_text=False, beam_size=5)
segs = []
for seg in segments:
    words = [{"start": round(w.start, 3), "end": round(w.end, 3), "word": w.word}
             for w in (seg.words or [])]
    if not words:
        continue
    segs.append({"start": round(seg.start, 3), "end": round(seg.end, 3),
                 "text": seg.text.strip(), "words": words})
doc = {"duration": round(info.duration, 3), "language": info.language,
       "language_probability": round(info.language_probability, 3), "segments": segs}
json.dump(doc, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
n_words = sum(len(s["words"]) for s in segs)
print("done in %.1fs: %d segments, %d words, duration=%.3f" % (time.time() - t0, len(segs), n_words, info.duration))
