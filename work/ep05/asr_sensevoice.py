#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""备用对词：SenseVoice+VAD 句级时间戳（快速、文本质量高）。
用途：①与 whisper 词级文本交叉核对；②whisper 超时/失败时的兜底。
注意：funasr 进程勿设 HF_HUB_OFFLINE（LESSONS E92）。"""
import json, time, torch
torch.set_num_threads(4)
from funasr import AutoModel

model = AutoModel(model="iic/SenseVoiceSmall", vad_model="fsmn-vad",
                  vad_kwargs={"max_single_segment_time": 30000},
                  device="cpu", disable_update=True)
t0 = time.time()
res = model.generate(input="media/ajfda_16k.wav", cache={}, language="auto", use_itn=True,
                     batch_size_s=60, merge_vad=True, merge_length_s=15, sentence_timestamp=True)
import re
segs = []
raw_text = res[0]["text"] if res else ""
for it in res[0].get("sentence_info", []):
    segs.append({"start": round(it["start"] / 1000, 3), "end": round(it["end"] / 1000, 3),
                 "text": re.sub(r"<\|[^|]*\|>", "", it["text"]).strip()})
doc = {"duration": 451.392, "engine": "sensevoice-small+fsmn-vad", "segments": segs}
json.dump(doc, open("transcript_sensevoice.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("sensevoice done %.1fs, %d sentences" % (time.time() - t0, len(segs)))
for s in segs[:8]:
    print("%7.2f %s" % (s["start"], s["text"][:40]))
