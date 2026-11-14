#!/usr/bin/env python3
"""video_breakdown.py — 本地视频拆解原型（CPU，无 GPU 可跑）。

把一条视频拆成三层可核对的数据：
  1) 硬切镜头（PySceneDetect；可选，缺失时用 ffmpeg scene 兜底）
  2) 画面段落（1fps 采样 + HSV 直方图/像素差；专治口播/动效视频没有硬切的情况）
  3) 口播分段（SenseVoice + fsmn-vad，带句级时间戳；可选）

输出:
  OUT/breakdown.json   机器可读
  OUT/report.md        人读时间线 + 口播稿
  OUT/keyframes/*.jpg  每段代表帧
  OUT/audio.wav        16k 单声道（ASR 用）

用法:
  python video_breakdown.py INPUT.mp4 -o OUT [--no-asr] [--no-visual]

依赖:
  - ffmpeg / ffprobe
  - scenedetect（硬切；pip install scenedetect）
  - opencv-python + numpy（画面段落扫描）
  - 可选: asr_segments.py + funasr/torch/soundfile 环境
    （脚本自动找 ~/src/compare-ocr-models-*/test/venv/bin/python，
    也可用环境变量 SENSEVOICE_PY 指定）

说明:
  - 硬切检测对渐变转场（动效模板常见的 dissolve/fade）会漏检，故另做画面段落扫描。
  - 画面段落是启发式分段，时间精度约 ±1s，用于“结构拆解”定位，不替代人工判断。
  - ASR 文本未经校对；SenseVoice 时间戳来自 VAD 段边界，不是逐字对齐。
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

DEFAULT_ASR_SH = os.path.expanduser("~/.local/sensevoice-asr/transcribe.sh")


def find_asr_python() -> str:
    """找带 funasr/torch 的 Python（可用 SENSEVOICE_PY 覆盖）。"""
    env = os.environ.get("SENSEVOICE_PY", "")
    if env and os.path.isfile(env):
        return env
    for p in glob.glob(os.path.expanduser("~/src/compare-ocr-models-*/test/venv/bin/python")):
        if os.path.isfile(p):
            return p
    return ""


DEFAULT_ASR_PY = find_asr_python()


def run(cmd: list[str], timeout: int | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def ffprobe(path: str) -> dict:
    r = run(["ffprobe", "-v", "error", "-print_format", "json",
             "-show_format", "-show_streams", path])
    if r.returncode != 0:
        raise RuntimeError(f"ffprobe 失败: {r.stderr.strip()[:500]}")
    data = json.loads(r.stdout)
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)

    def parse_rate(v: str | None) -> float:
        if not v or "/" not in v:
            return 0.0
        num, den = v.split("/", 1)
        return round(float(num) / float(den), 3) if float(den) else 0.0

    return {
        "path": os.path.abspath(path),
        "filename": os.path.basename(path),
        "duration": round(float(data.get("format", {}).get("duration", 0)), 3),
        "size_bytes": int(data.get("format", {}).get("size", 0)),
        "width": int(video.get("width", 0)),
        "height": int(video.get("height", 0)),
        "fps": parse_rate(video.get("avg_frame_rate")),
        "video_codec": video.get("codec_name"),
        "audio_codec": audio.get("codec_name") if audio else None,
    }


def detect_shots(video: str, duration: float, threshold: float, min_scene_len: int) -> tuple[list[dict], float, str, str]:
    """硬切检测：优先 PySceneDetect，失败/缺失时 ffmpeg fallback。"""
    t0 = time.time()
    try:
        from scenedetect import detect, ContentDetector  # type: ignore
        scenes = detect(video, ContentDetector(threshold=threshold, min_scene_len=min_scene_len))
        shots = [{"start": round(s[0].seconds, 3), "end": round(s[1].seconds, 3)} for s in scenes]
        elapsed = round(time.time() - t0, 2)
        if shots:
            return shots, elapsed, "scenedetect", f"PySceneDetect ContentDetector(threshold={threshold})"
        return [], elapsed, "scenedetect", "PySceneDetect ContentDetector 未发现硬切"
    except Exception as e:  # noqa: BLE001
        note = f"PySceneDetect 不可用（{type(e).__name__}），改用 ffmpeg scene"
    t0 = time.time()
    r = run(["ffmpeg", "-hide_banner", "-i", video,
             "-vf", "select='gt(scene,0.3)',showinfo", "-f", "null", "-"])
    times = [float(x) for x in re.findall(r"pts_time:([0-9.]+)", r.stderr)]
    cuts = sorted({round(t, 2) for t in times if 0.2 < t < duration - 0.2})
    shots = []
    prev = 0.0
    for t in cuts:
        if t - prev >= 0.4:
            shots.append({"start": round(prev, 3), "end": round(t, 3)})
            prev = t
    if prev < duration:
        shots.append({"start": round(prev, 3), "end": round(duration, 3)})
    return shots, round(time.time() - t0, 2), "ffmpeg", note + "（阈值 0.3）"


def scan_visual_changes(video: str, duration: float, out_dir: Path,
                        threshold: float = 0.16, max_scan_frames: int = 1800,
                        hard_cuts: int = 0) -> tuple[list[dict], float, dict]:
    """1fps 采样，HSV 直方图距离 + 灰度差，找画面/版面/文字块切换点。

    口播、口播+贴纸、动效模板这类视频常常没有硬切，PySceneDetect 会返回
    整段 1 个镜头；这个扫描把“整段画面”切成可读的段落。
    """
    import cv2  # type: ignore
    import numpy as np

    tmp = out_dir / "_scan"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True, exist_ok=True)
    fps = 1.0 if duration <= max_scan_frames else max(0.1, max_scan_frames / max(duration, 1.0))
    r = run(["ffmpeg", "-v", "error", "-i", video, "-vf", f"fps={fps:g},scale=360:-2",
             str(tmp / "%04d.jpg")], timeout=1800)
    if r.returncode != 0:
        return [], 0.0, {"median_shift_px": 0.0, "median_score": 0.0,
                         "stable": True, "reason": "1fps 抽帧失败，已跳过画面段落扫描"}
    files = sorted(tmp.glob("*.jpg"))
    points: list[dict] = []
    shifts: list[float] = []
    all_scores: list[float] = []
    prev_hist = prev_gray = prev_float = None
    last_t = -99.0
    for i, f in enumerate(files):
        img = cv2.imread(str(f))
        if img is None:
            continue
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [32, 32], [0, 180, 0, 256])
        cv2.normalize(hist, hist)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        if prev_hist is not None:
            hist_dist = float(cv2.compareHist(prev_hist, hist, cv2.HISTCMP_BHATTACHARYYA))
            abs_diff = float(cv2.absdiff(gray, prev_gray).mean() / 255.0)
            score = max(hist_dist, abs_diff * 8.0)
            all_scores.append(score)
            try:
                (dx, dy), _resp = cv2.phaseCorrelate(prev_float, gray.astype(np.float32))
                shifts.append(float((dx * dx + dy * dy) ** 0.5))
            except Exception:  # noqa: BLE001
                pass
            t = i / fps  # 第 i 帧与第 i-1 帧之间的切换，约发生在 i 秒
            if score >= threshold and t - last_t >= 2.0:
                points.append({"time": round(t, 2), "score": round(score, 3)})
                last_t = t
        prev_hist, prev_gray = hist, gray
        prev_float = gray.astype(np.float32)
    shutil.rmtree(tmp, ignore_errors=True)
    median_shift = round(float(np.median(shifts)), 2) if shifts else 0.0
    median_score = round(float(np.median(all_scores)), 3) if all_scores else 0.0
    stable = median_shift <= 2.0
    reason = ""
    if hard_cuts > 0:
        # 已有硬切时以硬切为准，不再用逐秒扫描去猜段落
        points = []
        reason = ""
    elif not stable:
        reason = "检测到明显镜头运动，已跳过画面段落扫描"
        points = []
    elif median_score > 0.35:
        reason = ("画面逐秒变化持续偏高（中位分 "
                  f"{median_score}），疑似真人口播/持续运动；"
                  "已跳过画面段落扫描，建议以口播分段为主")
        points = []
    return points, round(fps, 2), {"median_shift_px": median_shift,
                                   "median_score": median_score,
                                   "stable": stable, "reason": reason}


def segments_from_changes(points: list[dict], duration: float) -> list[dict]:
    bounds = [0.0] + [p["time"] for p in points] + [duration]
    segs = []
    for i in range(len(bounds) - 1):
        start, end = bounds[i], bounds[i + 1]
        if end - start < 1.0:
            continue
        segs.append({"index": len(segs), "start": round(start, 2), "end": round(end, 2),
                     "duration": round(end - start, 2)})
    return segs


def extract_keyframes(video: str, segs: list[dict], out_dir: Path, width: int = 640) -> list[dict]:
    kf_dir = out_dir / "keyframes"
    kf_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for s in segs:
        mid = (s["start"] + s["end"]) / 2.0
        name = f"seg{s['index']:02d}_{int(mid):04d}s.jpg"
        target = kf_dir / name
        r = run(["ffmpeg", "-v", "error", "-ss", f"{mid:.2f}", "-i", video,
                 "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", "3",
                 str(target), "-y"], timeout=120)
        if r.returncode == 0 and target.exists():
            rows.append({"segment": s["index"], "time": round(mid, 2),
                         "path": str(target.relative_to(out_dir))})
    return rows


def extract_audio(video: str, out_dir: Path) -> str | None:
    wav = out_dir / "audio.wav"
    r = run(["ffmpeg", "-v", "error", "-i", video, "-vn", "-ac", "1", "-ar", "16000",
             "-c:a", "pcm_s16le", str(wav), "-y"], timeout=600)
    return str(wav) if r.returncode == 0 and wav.exists() else None


def run_asr(wav: str, out_dir: Path, language: str,
            asr_py: str, asr_script: str) -> tuple[list[dict], dict]:
    """优先用 asr_segments.py 拿句级时间戳；退回现成 transcribe.sh 只有全文。"""
    t0 = time.time()
    if os.path.isfile(asr_py) and os.path.isfile(asr_script):
        out_json = out_dir / "asr.json"
        r = run([asr_py, asr_script, wav, str(out_json), "--language", language], timeout=3600)
        if r.returncode == 0 and out_json.exists():
            data = json.loads(out_json.read_text(encoding="utf-8"))
            return data.get("segments", []), {
                "engine": data.get("model", "SenseVoice"),
                "elapsed": round(time.time() - t0, 2),
                "infer_sec": data.get("infer_sec"),
                "note": "句级时间戳来自 VAD 段边界；文本未经人工校对",
            }
        note = (r.stderr or r.stdout or "")[-400:]
    else:
        note = f"未找到 {asr_py} 或 {asr_script}"
    if os.path.isfile(DEFAULT_ASR_SH):
        txt = out_dir / "asr.txt"
        r = run([DEFAULT_ASR_SH, wav, str(txt)], timeout=3600)
        if r.returncode == 0 and txt.exists():
            text = txt.read_text(encoding="utf-8").strip()
            return [], {"engine": "SenseVoice (transcribe.sh)",
                        "elapsed": round(time.time() - t0, 2),
                        "note": "该入口只输出全文，无时间戳；" + note}
    return [], {"engine": "none", "elapsed": round(time.time() - t0, 2), "note": note}


def overlap_idxs(seg: dict, asr: list[dict]) -> str:
    idxs = [f"S{i+1}" for i, a in enumerate(asr)
            if a["end"] >= seg["start"] and a["start"] <= seg["end"]]
    return "/".join(idxs) if idxs else "—"


def write_report(out_dir: Path, meta: dict, result: dict) -> Path:
    shots = result["shots"]
    vsegs = result["visual_segments"]
    asr = result["asr_segments"]
    kfs = {k["segment"]: k for k in result["keyframes"]}
    md = []
    md.append(f"# 视频拆解：{meta['filename']}\n")
    md.append(f"> 生成时间 {datetime.now().strftime('%Y-%m-%d %H:%M')}；"
              f"本报告为自动拆解初稿，ASR 文本未经校对，分段为启发式结果。\n")
    md.append("## 一、素材信息\n")
    md.append("| 项目 | 值 |\n|---|---|")
    md.append(f"| 时长 | {meta['duration']:.2f}s |")
    md.append(f"| 分辨率 / 帧率 | {meta['width']}×{meta['height']} / {meta['fps']:g}fps |")
    md.append(f"| 视频编码 | {meta['video_codec']} |")
    size_mb = meta['size_bytes'] / 1024 / 1024
    size_str = f"{size_mb:.1f} MB" if size_mb >= 1 else f"{meta['size_bytes']/1024:.0f} KB"
    md.append(f"| 文件大小 | {size_str} |")
    md.append("")
    detect = result["detect"]
    mode = result.get("visual_mode", "none")
    mode_label = {"changes": "1fps 扫描", "shots": "硬切回退", "skipped": "未扫描", "none": "未扫描"}.get(mode, mode)
    md.append("## 二、拆解信号\n")
    md.append("| 信号 | 结果 | 用时 |\n|---|---|---|")
    md.append(f"| 硬切 | {detect['hard_cuts']} 个切点（{len(shots)} 个镜头） | {detect['shots_elapsed']}s |")
    md.append(f"| 画面段落 | {len(vsegs)} 段（{mode_label}） | {detect['visual_elapsed']}s |")
    infer = result['asr_meta'].get('infer_sec')
    infer_note = f"（其中模型加载约 {max(0.0, result['asr_meta']['elapsed'] - infer):.1f}s，推理 {infer:.1f}s）" if infer else ""
    md.append(f"| 口播分段 | {len(asr)} 段 | {result['asr_meta']['elapsed']}s |")
    if infer_note:
        md.append(f"\n> 口播耗时 {result['asr_meta']['elapsed']}s{infer_note}；"
                  "单条视频的主要开销是首次加载模型，批量处理建议复用常驻进程。\n")
    md.append("")
    if detect.get("hard_cuts", 0) == 0:
        md.append("> 未检测到硬切：这条视频很可能是单镜头口播，或动效/渐变转场。"
                  "此时**不要**把“0 个切点”当成拆解失败，应看下面的画面段落与口播分段。\n")
    md.append("## 三、画面段落时间线\n")
    if vsegs:
        md.append("| # | 起止 | 时长 | 画面代表帧 | 覆盖口播段 |")
        md.append("|---|---|---|---|---|")
        for s in vsegs:
            kf = kfs.get(s["index"])
            kf_cell = f"[{Path(kf['path']).name}]({kf['path']})" if kf else "—"
            covered = overlap_idxs(s, asr) if asr else "—"
            md.append(f"| {s['index']+1} | {s['start']:.1f}–{s['end']:.1f}s | {s['duration']:.1f}s | {kf_cell} | {covered} |")
        md.append("")
        md.append("> 画面段落基于 1fps 采样的直方图/像素差，适合定位“整版换字/换场景”，"
                  "精度约 ±1s；连续缓慢的运镜不会触发。\n")
    if result["visual_stability"].get("reason"):
        md.append(f"> {result['visual_stability']['reason']}。\n")
    elif not vsegs:
        md.append("（未启用画面扫描，或视频无显著画面变化。）\n")
    md.append("## 四、口播分段（ASR 初稿）\n")
    if asr:
        md.append("| 起止 | 文本 |\n|---|---|")
        for a in asr:
            md.append(f"| {a['start']:.1f}–{a['end']:.1f}s | {a['text']} |")
        md.append("")
        md.append("> 时间戳来自 fsmn-vad 语音段边界，句内无逐字对齐；"
                  "文本为 SenseVoice 自动转写，专有名词/同音字可能出错，引用前需校对。\n")
    else:
        md.append(f"（未获得带时间戳的转写：{result['asr_meta']['note']}）\n")
    md.append("## 五、结构拆解模板（待人工/LLM 填写）\n")
    md.append("按上面时间线，把每一段填进下面四栏；口播类视频通常对应：\n")
    md.append("| 结构位 | 时间 | 这一段在做什么 | 画面/字幕 |")
    md.append("|---|---|---|---|")
    md.append("| 钩子（0–3s） |  | 提出什么问题/反常识结论 |  |")
    md.append("| 立论/展开 |  | 观点与论据 |  |")
    md.append("| 例证/演示 |  | 产品、对比、数据 |  |")
    md.append("| 行动号召（结尾） |  | 让观众做什么 |  |")
    md.append("")
    md.append("## 六、方法与局限\n")
    md.append("- 硬切：PySceneDetect ContentDetector（阈值 "
              f"{result['detect']['threshold']}），只擅长硬切；渐变/叠化会漏检。")
    md.append("- 画面段落：1fps 采样 + HSV 直方图距离（Bhattacharyya）+ 灰度差，"
              "阈值 0.16，间隔 <2s 的合并；用于结构定位，不是镜头语言级分镜。")
    md.append("- 口播：SenseVoice-small（CPU）+ fsmn-vad；本机已缓存模型，可离线跑。")
    md.append("- 未做的：景别/运镜分类、OCR 画面文字、说话人分离、情感/节奏曲线。")
    md.append("")
    md.append("## 七、复跑\n")
    md.append("```bash")
    md.append(f"python {Path(__file__).name} \"{meta['path']}\" -o \"{out_dir}\"")
    md.append("```")
    path = out_dir / "report.md"
    path.write_text("\n".join(md), encoding="utf-8")
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description="本地视频拆解（硬切 + 画面段落 + 口播分段）")
    ap.add_argument("input")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--threshold", type=float, default=27.0, help="PySceneDetect 内容阈值")
    ap.add_argument("--min-scene-len", type=int, default=15, help="最短镜头帧数")
    ap.add_argument("--visual-threshold", type=float, default=0.16, help="画面段落阈值")
    ap.add_argument("--no-visual", action="store_true")
    ap.add_argument("--no-asr", action="store_true")
    ap.add_argument("--language", default="auto")
    ap.add_argument("--asr-python", default=os.environ.get("SENSEVOICE_PY", DEFAULT_ASR_PY))
    ap.add_argument("--asr-script", default=os.environ.get(
        "ASR_SEGMENTS_SCRIPT", str(Path(__file__).with_name("asr_segments.py"))))
    ap.add_argument("--keyframe-width", type=int, default=640)
    args = ap.parse_args()

    video = os.path.abspath(args.input)
    if not os.path.isfile(video):
        print(f"[err] 找不到视频: {video}", file=sys.stderr)
        return 2
    out_dir = Path(args.output).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    t_all = time.time()
    meta = ffprobe(video)
    print(f"[info] {meta['filename']}  {meta['duration']:.1f}s  {meta['width']}x{meta['height']}@{meta['fps']:g}")

    print("[1/4] 硬切检测 ...")
    shots, shots_elapsed, engine, note = detect_shots(
        video, meta["duration"], args.threshold, args.min_scene_len)
    if not shots:
        shots = [{"start": 0.0, "end": meta["duration"]}]
        hard_cuts = 0
        shots_note = note + "；整段按 1 个镜头处理"
    else:
        hard_cuts = len(shots) - 1 if not (len(shots) == 1 and shots[0]["start"] < 0.1) else 0
        shots_note = note
    print(f"      {hard_cuts} 个切点 / {len(shots)} 个镜头 / {shots_elapsed}s ({engine})")

    print("[2/4] 画面段落扫描 ...")
    visual_stability = {"median_shift_px": 0.0, "stable": True}
    if args.no_visual:
        points, visual_elapsed = [], 0.0
    else:
        points, visual_elapsed, visual_stability = scan_visual_changes(
            video, meta["duration"], out_dir, args.visual_threshold, hard_cuts=hard_cuts)
    vsegs = segments_from_changes(points, meta["duration"]) if points else segments_from_changes([], meta["duration"])
    # 若无显著画面变化，用镜头表作为段落表（单镜头时即整段一段）
    if not points:
        vsegs = [{"index": i, "start": round(s["start"], 2), "end": round(s["end"], 2),
                  "duration": round(s["end"] - s["start"], 2)} for i, s in enumerate(shots)]
    print(f"      {len(points)} 个变化点 -> {len(vsegs)} 段 / {visual_elapsed}s")

    print("[3/4] 抽关键帧 ...")
    keyframes = extract_keyframes(video, vsegs, out_dir, args.keyframe_width)
    print(f"      {len(keyframes)} 张")

    print("[4/4] 口播转写 ...")
    asr_segments, asr_meta = [], {"engine": "skipped", "elapsed": 0.0, "note": "--no-asr"}
    if not args.no_asr:
        wav = extract_audio(video, out_dir)
        if wav:
            asr_segments, asr_meta = run_asr(
                wav, out_dir, args.language, args.asr_python, args.asr_script)
        else:
            asr_meta = {"engine": "none", "elapsed": 0.0, "note": "抽音频失败"}
    print(f"      {len(asr_segments)} 段 ({asr_meta['engine']}, {asr_meta['elapsed']}s)")

    if points:
        visual_mode = "changes"
    elif hard_cuts > 0:
        visual_mode = "shots"
    elif visual_stability.get("reason"):
        visual_mode = "skipped"
    else:
        visual_mode = "none"
    result = {
        "schema_version": "0.1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": meta,
        "detect": {
            "engine": engine,
            "threshold": args.threshold,
            "note": shots_note,
            "hard_cuts": hard_cuts,
            "shots_elapsed": shots_elapsed,
            "visual_elapsed": visual_elapsed,
        },
        "shots": shots,
        "visual_changes": points,
        "visual_mode": visual_mode,
        "visual_stability": visual_stability,
        "visual_segments": vsegs,
        "keyframes": keyframes,
        "asr_meta": asr_meta,
        "asr_segments": asr_segments,
        "total_elapsed": round(time.time() - t_all, 2),
    }
    (out_dir / "breakdown.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    report = write_report(out_dir, meta, result)
    print(f"[ok] {report}")
    print(f"[ok] total {result['total_elapsed']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
