#!/usr/bin/env python3
"""SenseVoice + fsmn-vad 句级转写（CPU）。

输出带时间戳的分段 JSON，供 video_breakdown.py 使用。默认使用本机已缓存的
iic/SenseVoiceSmall + fsmn-vad 模型（~/.cache/modelscope），离线可跑。

用法（需 funasr + torch + soundfile 的环境，本机为
~/src/compare-ocr-models-8ca7b0b3fd79/test/venv/bin/python）:

    python asr_segments.py audio.wav out.json [--language auto]

输出:
    {"language": "auto", "segments": [{"start": 0.02, "end": 11.42, "text": "..."}, ...]}

注意: SenseVoice 本身不输出词级时间戳；这里的时间戳来自 fsmn-vad 的语音段
边界，粒度约等于一句话/一个停顿段，不是逐字对齐。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

TAG_RE = re.compile(r"<\|[^|]*\|>")
SR = 16000


def clean_text(raw: str) -> str:
    return TAG_RE.sub("", raw).strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("wav")
    ap.add_argument("out")
    ap.add_argument("--language", default="auto")
    ap.add_argument("--threads", type=int, default=6)
    args = ap.parse_args()

    wav = os.path.abspath(args.wav)
    if not os.path.isfile(wav):
        print(f"[err] 找不到音频: {wav}", file=sys.stderr)
        return 2
    os.environ.setdefault("HF_HUB_OFFLINE", "1")

    import soundfile as sf
    import torch
    from funasr import AutoModel

    torch.set_num_threads(args.threads)
    t0 = time.time()
    vad = AutoModel(model="fsmn-vad", device="cpu", disable_update=True)
    vad_out = vad.generate(input=wav)
    segments = vad_out[0].get("value", []) if vad_out else []

    data, sr = sf.read(wav, dtype="float32")
    if sr != SR:
        print(f"[err] 采样率需为 {SR}Hz，实际 {sr}Hz", file=sys.stderr)
        return 2
    if data.ndim > 1:
        data = data.mean(axis=1)

    model = AutoModel(model="iic/SenseVoiceSmall", device="cpu", disable_update=True)
    rows = []
    infer_t0 = time.time()
    for start_ms, end_ms in segments:
        chunk = data[int(start_ms / 1000 * SR): int(end_ms / 1000 * SR)]
        if len(chunk) < SR // 10:
            continue
        res = model.generate(
            input=chunk, cache={}, language=args.language,
            use_itn=True, batch_size_s=60,
        )
        text = clean_text(res[0].get("text", "")) if res else ""
        if text:
            rows.append({
                "start": round(start_ms / 1000.0, 2),
                "end": round(end_ms / 1000.0, 2),
                "text": text,
            })

    payload = {
        "language": args.language,
        "model": "iic/SenseVoiceSmall + fsmn-vad",
        "duration": round(len(data) / SR, 2),
        "segments": rows,
        "elapsed_sec": round(time.time() - t0, 2),
        "infer_sec": round(time.time() - infer_t0, 2),
        "note": "时间戳来自 fsmn-vad 语音段边界，不是逐字对齐；文本未经人工校对。",
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"[ok] {len(rows)} 段 -> {args.out} ({payload['elapsed_sec']}s, rtf={payload['elapsed_sec']/max(payload['duration'],0.01):.3f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
