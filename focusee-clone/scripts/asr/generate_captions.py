#!/usr/bin/env python3
"""句级时间戳字幕生成（SenseVoice-small + fsmn-vad，本机 CPU，离线可用）。

用法: python3 generate_captions.py <音频/视频文件> <out.json> [--language auto]
      输入建议先用 ffmpeg 抽成 16k 单声道 wav（调用方 main.js 已做）。

输出: <out.json> 写入 [{"start": 秒, "end": 秒, "text": "..."}, ...]
      stdout 打印人类可读进度/摘要（供日志），JSON 只落文件。

实现：先 fsmn-vad 切出带时间戳的语音段，再逐段喂 SenseVoice 转写——
SenseVoice 本身不输出词级时间戳，VAD 段边界即字幕时间轴（标准 funasr 用法）。
依赖: funasr + torch（本机 venv 由 main.js 解析并传入），模型缓存
~/.cache/modelscope（iic/SenseVoiceSmall + fsmn-vad），离线可用。
"""
import argparse
import json
import os
import re
import sys
import time

os.environ.setdefault("HF_HUB_OFFLINE", "1")

TAG_RE = re.compile(r"<\|[^|]*\|>")
MIN_SEGMENT_S = 0.2  # 比 200ms 还短的「语音段」是呼吸/噪声，丢弃
MAX_CAPTION_CHARS = 42  # 一条字幕的字符上限，超了按标点切句（近似时间分配）
MAX_ASR_CHUNK_S = 60.0  # 单段音频超过这个才硬切（保护识别质量，罕见）


def log(msg: str) -> None:
    print(msg, flush=True)


def load_wav(path: str):
    """Return (samples float32 in [-1,1], sample_rate) for a PCM wav."""
    import wave

    import numpy as np

    with wave.open(path, "rb") as w:
        rate = w.getframerate()
        n = w.getnframes()
        ch = w.getnchannels()
        width = w.getsampwidth()
        raw = w.readframes(n)
    if width != 2:
        raise SystemExit(f"unsupported wav sample width: {width} (expect 16-bit; caller must resample)")
    samples = np.frombuffer(raw, dtype=np.int16)
    if ch > 1:
        samples = samples.reshape(-1, ch).mean(axis=1)
    return (samples.astype("float32") / 32768.0), rate


def _find_cut(text: str, pos: int) -> int:
    """在 pos 附近（±8 字）找标点作为切点，优先句级标点，其次逗号顿号。"""
    wstart = max(0, pos - 8)
    window = text[wstart:pos + 8]
    best = None
    for j, ch in enumerate(window):
        if ch in "。！？；?!;":
            best = j
            break
    if best is None:
        for j, ch in enumerate(window):
            if ch in "，,、：:":
                best = j
                break
    cut = wstart + best + 1 if best is not None else pos
    return max(1, min(cut, len(text) - 1))


def split_long_caption(beg: float, end: float, text: str):
    """一条字幕过长时切成多条：文本按标点切，时间按各段字数比例近似分配。"""
    n = max(1, -(-len(text) // MAX_CAPTION_CHARS))  # ceil
    if n == 1:
        return [(beg, end, text)]
    target = len(text) / n
    cuts = []
    for i in range(1, n):
        pos = min(len(text) - 4 * (n - i), int(round(i * target)))
        cuts.append(_find_cut(text, pos))
    pieces = []
    prev = 0
    for c in cuts + [len(text)]:
        piece = text[prev:c].strip()
        prev = c
        if piece:
            pieces.append(piece)
    total = sum(len(p) for p in pieces) or 1
    out = []
    acc = 0.0
    for p in pieces:
        span = (end - beg) * (len(p) / total)
        out.append((beg + acc, beg + acc + span, p))
        acc += span
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("out")
    ap.add_argument("--language", default="auto")
    ap.add_argument("--max-segment-s", type=float, default=MAX_ASR_CHUNK_S)
    args = ap.parse_args()

    t0 = time.time()
    log(f"[asr] loading pcm: {args.audio}")
    pcm, rate = load_wav(args.audio)
    dur = len(pcm) / rate
    log(f"[asr] pcm {dur:.1f}s @ {rate}Hz")

    from funasr import AutoModel

    log("[asr] loading models (SenseVoiceSmall + fsmn-vad)…")
    vad = AutoModel(model="fsmn-vad", device="cpu", disable_update=True)
    asr = AutoModel(model="iic/SenseVoiceSmall", device="cpu", disable_update=True)
    log(f"[asr] models ready in {time.time() - t0:.1f}s")

    # 1) VAD：毫秒级语音段边界（[[beg,end],...]）
    res = vad.generate(input=pcm, fs=rate, cache={}, disable_pbar=True)
    spans = res[0].get("value") if res and res[0].get("value") else []
    if not spans:
        log("[asr] no speech segments detected")
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False)
        return 0

    # 2) 超长语音段才硬切（VAD 平时会在停顿处切好，极少走到这里）
    segs = []
    for beg_ms, end_ms in spans:
        beg, end = beg_ms / 1000.0, end_ms / 1000.0
        if end - beg < MIN_SEGMENT_S:
            continue
        if end - beg <= args.max_segment_s:
            segs.append((beg, end))
            continue
        n = int(-(-(end - beg) // args.max_segment_s))  # ceil
        step = (end - beg) / n
        for i in range(n):
            segs.append((beg + i * step, beg + (i + 1) * step))

    # 3) 逐段转写；过长文本按标点切成字幕尺度的句子
    out = []
    asr_t0 = time.time()
    for i, (beg, end) in enumerate(segs):
        lo, hi = int(beg * rate), int(end * rate)
        chunk = pcm[lo:hi]
        if not len(chunk):
            continue
        r = asr.generate(input=chunk, fs=rate, cache={}, language=args.language,
                         use_itn=True, disable_pbar=True)
        text = TAG_RE.sub("", r[0].get("text", "") if r else "").strip()
        if not text:
            continue
        for b2, e2, t2 in split_long_caption(beg, end, text):
            out.append({"start": round(b2, 2), "end": round(e2, 2), "text": t2})
        if (i + 1) % 5 == 0 or i + 1 == len(segs):
            log(f"[asr] {i + 1}/{len(segs)} segments done")

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    log(f"[asr] wrote {len(out)} captions -> {args.out} "
        f"(asr {time.time() - asr_t0:.1f}s, total {time.time() - t0:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
