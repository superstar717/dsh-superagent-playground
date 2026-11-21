#!/usr/bin/env python3
"""PC 端口播视频驱动：edge-tts 配音 → captions → 模板 #385712 渲染链 + 状态心跳。

在 PC（Windows）上运行：
  python oral_build.py --job-dir D:\\oral\\jobs\\20261121-pc-llm-setup --template D:\\oral\\tools\\pkg

前置：node.exe/ffmpeg.exe 已装（本脚本自动探测 PATH 与 winget 目录）；pip install edge-tts uv。
状态：每步原子写 <job>/90-meta/status.json（≤10s 心跳，Mac 端 oral-fetch-status.sh 拉取看板）。
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

JOB_NAME = "20261121-pc-llm-setup"
STATE = {"stage": "init", "state": "running", "percent": 0, "step": "", "eta_s": None}
STATE_LOCK = threading.Lock()
SCRIPT_LINES = [
    "我们的目标很简单：在一台 RTX 3060 的电脑上，跑起自己的本地大模型。",
    "第一步打好地基：清出四十多G系统盘，引擎走局域网分发，绕开八个G的编译坑。",
    "三十五B的模型量化后只有十一点七G，放进固态硬盘；实测每秒四十多个token，显存刚好塞满。",
    "从消息到模型，全链路已经打通。下一步，内存升到六十四G，挑战一千两百五十亿参数。",
]
SCENE_DUR = {"B1": 8.0, "B2": 10.0, "B3": 10.0, "B4": 8.0}


def write_status(job_dir: Path) -> None:
    meta = job_dir / "90-meta"
    meta.mkdir(parents=True, exist_ok=True)
    with STATE_LOCK:
        data = {
            "job": JOB_NAME,
            "stage": STATE["stage"],
            "step": STATE["step"],
            "percent": STATE["percent"],
            "state": STATE["state"],
            "owner": "pc",
            "host": socket.gethostname(),
            "pid": os.getpid(),
            "started_at": getattr(write_status, "started", ""),
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "eta_s": STATE["eta_s"],
            "next": "",
            "error": None,
        }
    fd, tmp = tempfile.mkstemp(dir=str(meta), prefix=".status-", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, meta / "status.json")


def set_state(stage: str, step: str, percent: float, state: str = "running") -> None:
    with STATE_LOCK:
        STATE.update(stage=stage, step=step, percent=int(percent), state=state)
    write_status(JOB_DIR)


def heartbeat(interval: float = 10.0) -> None:
    write_status(JOB_DIR)
    t = threading.Event()
    while not t.wait(interval):
        write_status(JOB_DIR)


def find_exe(names: list[str]) -> str:
    """在 PATH、固定工具目录与 winget 包目录里找可执行文件。"""
    dirs: list[str] = []
    dirs += os.environ.get("PATH", "").split(os.pathsep)
    dirs += ["D:\\oral\\tools"]  # 本工单固定工具目录（含子目录递归）
    winget_pkgs = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    links = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links"
    for root in (links, winget_pkgs):
        if root.is_dir():
            for dirpath, _dirnames, _files in os.walk(root):
                dirs.append(dirpath)
                if len(dirs) > 400:
                    break
    tools_root = Path("D:\\oral\\tools")
    if tools_root.is_dir():
        for dirpath, dirnames, _files in os.walk(tools_root):
            dirs.append(dirpath)
            dirnames[:] = [d for d in dirnames if d.lower() not in ("node_modules",)]  # 跳过巨目录
    for name in names:
        for d in dirs:
            candidate = Path(d) / name
            if candidate.is_file():
                return str(candidate)
    raise FileNotFoundError(f"none of {names} found; searched {len(dirs)} dirs")


def err_tail_lines(text: str) -> str:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    errs = [l for l in lines if ("Error" in l or "error:" in l)]
    return (errs[-1] if errs else lines[-1] if lines else "unknown")[:160]


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    print("[cmd]", " ".join(cmd), flush=True)
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def tts_segments(ffmpeg: str, ffprobe: str) -> list[dict]:
    """逐句 edge-tts 合成 → 转 48k wav → 按序拼接，返回每句起止（秒）。"""
    import edge_tts  # noqa: PLC0415

    async def synth(text: str, mp3: Path) -> None:
        import asyncio

        tts = edge_tts.Communicate(text, voice="zh-CN-YunxiNeural", rate="+4%")
        await tts.save(str(mp3))

    import asyncio

    segs = []
    for i, text in enumerate(SCRIPT_LINES):
        mp3 = JOB_DIR / "10-tts" / f"seg_{i:02d}.mp3"
        mp3.parent.mkdir(parents=True, exist_ok=True)
        asyncio.run(synth(text, mp3))
        wav = mp3.with_suffix(".wav")
        r = run([ffmpeg, "-y", "-i", str(mp3), "-ar", "48000", "-ac", "2", str(wav)])
        if r.returncode != 0:
            raise RuntimeError(f"ffmpeg wav convert failed: {r.stderr[-300:]}")
        dur = float(json.loads(run([ffprobe, "-v", "error", "-show_entries",
                                   "format=duration", "-of", "json", str(wav)]).stdout
                              )["format"]["duration"])
        segs.append({"wav": wav, "dur": dur, "text": text})
        print(f"[tts] seg{i} {dur:.2f}s", flush=True)
    return segs


def concat_and_captions(segs: list[dict], ffmpeg: str) -> tuple[Path, list[dict]]:
    """拼接全部句段（句间 0.35s），生成 captions（含整窗句组）。"""
    gap = 0.35
    concat_list = JOB_DIR / "10-tts" / "concat.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        for s in segs:
            f.write(f"file '{s['wav'].as_posix()}'\n")
            f.write(f"file '{SILENCE.as_posix()}'\n")
    voice = JOB_DIR / "00-input" / "voice.wav"
    r = run([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
             "-c", "copy", str(voice)])
    if r.returncode != 0:
        raise RuntimeError(f"concat failed: {r.stderr[-300:]}")
    captions, t = [], 0.0
    for s in segs:
        captions.append({"start": round(t, 3), "end": round(t + s["dur"], 3), "text": s["text"]})
        t += s["dur"] + gap
    total = t - gap
    return voice, captions, total


SCENE_TITLES = {"B1": "PC本地大模型", "B2": "先把地基打好", "B3": "35B跑起来了", "B4": "下一步125B"}


def build_user_json(captions: list[dict], total: float) -> dict:
    """把各句时长分配到 B1-B4：每组 duration = 基础时长（句若溢出再调 reading hold）。"""
    scenes = []
    for sid, base in SCENE_DUR.items():
        scenes.append({"id": sid, "title": SCENE_TITLES[sid], "duration": round(base, 1)})
    mark_windows = []
    t0 = sum(SCENE_DUR[s["id"]] for s in scenes[:2])
    mark_windows.append({"start": round(t0 + 1.0, 1), "end": round(t0 + 6.5, 1)})
    return {
        "mode": "user-media",
        "language": "zh",
        "layout": "landscape",
        # duration 必须等于所选原生窗口之和（B1-B4 基础 36s）；配音不足由 pad_voice 补齐
        "duration": round(sum(SCENE_DUR.values()), 1),
        "title": "在 PC 上搭建本地大模型",
        "presenterLabel": "",
        "scenes": scenes,
        "content": {},
        "basic": {
            "keyword": "PC本地大模型",
            "explanation": "RTX 3060\n12G显存就够",
            "heading": "先把地基打好",
            "points": ["C盘腾出47G", "引擎局域网分发", "绕开CUDA编译", "35B放进SSD"],
            "left": "量化11.7G",
            "right": "每秒45tok",
            "conclusion": "从清理C盘到跑通模型，一台12G显存的PC就够",
            "summary": "全链路打通",
            "action": "下一步：64G内存\n上125B大模型",
        },
        "media": {
            "presenter": {"mode": "none"},
            "voice": {"mode": "file", "file": "voice.wav"},
            "music": {"mode": "none"},
        },
        "soundEffects": "native",
        "captions": captions,
        "markWindows": mark_windows,
    }


def main() -> int:
    global JOB_DIR, SILENCE
    ap = argparse.ArgumentParser()
    ap.add_argument("--job-dir", required=True)
    ap.add_argument("--template", required=True, help="模板 pkg 目录（含 adapter.py/render.mjs/node_modules）")
    ap.add_argument("--skip-tts", action="store_true", help="复用已有 voice.wav（调试用）")
    args = ap.parse_args()
    JOB_DIR = Path(args.job_dir)
    template = Path(args.template)
    write_status.started = datetime.now(timezone.utc).isoformat(timespec="seconds")

    ffmpeg = find_exe(["ffmpeg.exe"])
    ffprobe = find_exe(["ffprobe.exe"])
    node = find_exe(["node.exe"])
    print(f"[env] ffmpeg={ffmpeg}\n[env] node={node}", flush=True)
    # render.mjs spawn('ffmpeg') 与 adapter spawn('node') 都依赖 PATH，注入两个工具目录
    os.environ["PATH"] = os.path.dirname(ffmpeg) + os.pathsep + os.path.dirname(node) + os.pathsep + os.environ.get("PATH", "")

    hb = threading.Thread(target=heartbeat, args=(10.0,), daemon=True)
    hb.start()

    SILENCE = JOB_DIR / "10-tts" / "gap.wav"
    SILENCE.parent.mkdir(parents=True, exist_ok=True)
    run([ffmpeg, "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", "0.35", str(SILENCE)])

    try:
        set_state("10-tts", "edge-tts 合成 4 句", 5)
        if (JOB_DIR / "00-input" / "voice.wav").is_file() and (JOB_DIR / "00-input" / "user.json").is_file():
            args.skip_tts = True   # 复用已有配音与 user.json（重跑场景）
        if args.skip_tts and (JOB_DIR / "00-input" / "voice.wav").is_file():
            segs = []
            t = 0.0
            for text in SCRIPT_LINES:
                wav = JOB_DIR / "10-tts" / f"seg_{len(segs):02d}.wav"
                dur = float(json.loads(run([ffprobe, "-v", "error", "-show_entries",
                                            "format=duration", "-of", "json", str(wav)]).stdout
                                      )["format"]["duration"])
                segs.append({"wav": wav, "dur": dur, "text": text})
                t += dur
            voice = JOB_DIR / "00-input" / "voice.wav"
            captions, total = [], 0.0
            for s in segs:
                captions.append({"start": round(total, 3), "end": round(total + s["dur"], 3), "text": s["text"]})
                total += s["dur"] + 0.35
            total -= 0.35
        else:
            segs = tts_segments(ffmpeg, ffprobe)
            voice, captions, total = concat_and_captions(segs, ffmpeg)
        print(f"[tts] total {total:.2f}s", flush=True)

        set_state("20-edit", "写 user.json + plan 校验", 25)
        import shutil
        for stale in ("plan.json", "instance"):
            for base in (JOB_DIR / "00-input", JOB_DIR):
                p_ = base / stale
                if p_.is_dir():
                    shutil.rmtree(p_, ignore_errors=True)
                elif p_.exists():
                    p_.unlink()
        for stale in (JOB_DIR / "30-render" / "silent.mp4",
                      JOB_DIR / "30-render" / "silent-with-audio.mp4",
                      JOB_DIR / "30-render" / "preview.png"):
            stale.unlink(missing_ok=True)
        user = build_user_json(captions, total)
        # 配音短于窗口总和时 pad_voice 自动补尾静音；超出超过 12s 才需要调 reading hold（当前不会发生）
        (JOB_DIR / "00-input").mkdir(parents=True, exist_ok=True)
        (JOB_DIR / "00-input" / "user.json").write_text(
            json.dumps(user, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        pad = run([sys.executable, str(template.parent / "pad_voice.py"),
                   str(JOB_DIR / "00-input" / "user.json"), str(JOB_DIR / "00-input")])
        if pad.returncode != 0:
            raise RuntimeError("pad_voice failed: " + (pad.stderr or pad.stdout)[-200:])

        env = {**os.environ, "NO_COLOR": "1"}
        UV = [sys.executable, "-m", "uv"]   # pip 安装的 uv 用 python -m 调用最稳
        def err_tail(r_) -> str:
            text = (r_.stderr or "") + "\n" + (r_.stdout or "")
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            errs = [l for l in lines if ("Error" in l or "error:" in l)]
            return (errs[-1] if errs else lines[-1] if lines else "unknown")[:160]

        for step, extra in (("plan", ["plan", "--input", str(JOB_DIR / "00-input" / "user.json"),
                                      "--out", str(JOB_DIR / "00-input" / "plan.json")]),
                            ("prepare", ["prepare", "--input", str(JOB_DIR / "00-input" / "user.json"),
                                         "--out", str(JOB_DIR / "00-input" / "instance")])):
            r = run(UV + ["run", str(template / "adapter.py")] + extra, env=env, cwd=str(template))
            if r.returncode != 0:
                raise RuntimeError(f"adapter {step} failed: {err_tail(r)}")

        set_state("30-render", "preview", 30)
        r = run(UV + ["run", str(template / "adapter.py"), "preview", "--instance",
                 str(JOB_DIR / "00-input" / "instance"), "--out", str(JOB_DIR / "30-render" / "preview.png"),
                 "--time", "3"], env=env, cwd=str(template))
        if r.returncode != 0:
            print("[warn] preview failed (non-fatal):", (r.stderr or "")[-200:], flush=True)

        set_state("30-render", "render 逐帧", 35)
        render_out = JOB_DIR / "30-render" / "silent.mp4"
        render_out.parent.mkdir(parents=True, exist_ok=True)
        r = subprocess.Popen(
            UV + ["run", str(template / "adapter.py"), "render", "--instance",
             str(JOB_DIR / "00-input" / "instance"), "--out", str(render_out)],
            env=env, cwd=str(template), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        frames_total = None
        rendered_lines: list[str] = []
        for line in r.stdout:
            line = line.strip()
            rendered_lines.append(line)
            if line.startswith('{"seconds"'):
                try:
                    j = json.loads(line)
                    if frames_total is None:
                        frames_total = j["total"]
                    pct = 35 + 55 * (j["seconds"] / max(0.1, j["total"]))
                    set_state("30-render", f"frame {j['seconds']:.0f}/{j['total']:.0f}s", pct)
                except json.JSONDecodeError:
                    pass
        r.wait()
        if r.returncode != 0:
            tail = "\n".join(rendered_lines[-8:])
            (JOB_DIR / "30-render" / "render-stdout.log").write_text(
                "\n".join(rendered_lines), encoding="utf-8", errors="replace")
            raise RuntimeError("render failed: " + err_tail_lines(tail))

        import shutil
        final = render_out.with_name("silent-with-audio.mp4")   # mix.py 输出在 render 输出同目录
        (JOB_DIR / "40-final").mkdir(parents=True, exist_ok=True)
        target = JOB_DIR / "40-final" / "final.mp4"
        if final.is_file():
            shutil.copy2(final, target)
            final = target
        elif target.is_file():
            final = target
        else:
            raise RuntimeError(f"final mp4 not found: expected {final}")

        set_state("40-final", "manifest 校验", 95)
        manifest = run([sys.executable, str(template.parent / "manifest.py"),
                        str(JOB_DIR / "00-input"), str(target), str(template.parent)])
        if manifest.returncode != 0:
            raise RuntimeError(f"manifest failed: {(manifest.stderr or manifest.stdout)[-400:]}")
        dur = float(json.loads(run([ffprobe, "-v", "error", "-show_entries",
                                    "format=duration", "-of", "json", str(final)]).stdout
                              )["format"]["duration"])
        set_state("40-final", f"done {dur:.1f}s → {final}", 100, state="done")
        print(f"[DONE] {final} ({dur:.2f}s)", flush=True)
        return 0
    except Exception as exc:  # noqa: BLE001
        with STATE_LOCK:
            STATE.update(state="failed", step=str(exc)[:180], error=str(exc)[:180])
        write_status(JOB_DIR)
        meta = JOB_DIR / "90-meta"
        (meta / "handoff.md").write_text(
            f"# 失败交接\n\n- 阶段：{STATE['stage']} {STATE['step']}\n- 错误：{exc}\n- 下一步：修完从失败段重跑\n",
            encoding="utf-8")
        print(f"[FAILED] {exc}", flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
