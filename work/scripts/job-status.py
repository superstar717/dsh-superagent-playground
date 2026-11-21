#!/usr/bin/env python3
"""口播任务看板：读 jobs/*/90-meta/status.json，一屏看清长任务卡在哪。

设计口径见 work/12G显存PC做口播视频-可行性与分工-2026-11-21.md 第 5 节：
- 每个阶段（stage）由当前 owner 机器每 ≤10 秒把 status.json 原子覆盖一次；
- 看板只读，不写状态，避免两台机器互相覆盖；
- 超过 stale 秒（默认 30）没有心跳的运行中任务标 STALE，失败标 FAILED。

用法：
  python3 job-status.py                          # 自动找 ~/oral/jobs 与 /Volumes/oral/jobs
  python3 job-status.py --root ~/oral/jobs       # 指定 job 根（可重复）
  python3 job-status.py --watch 15               # 每 15 秒刷新
  python3 job-status.py --json                   # 机器可读
  python3 job-status.py --hide-done              # 只看在跑的
  python3 job-status.py --stale 60               # 自定义心跳超时

退出码：0 全部正常；1 有 FAILED 或 STALE；2 job 根不存在。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

DEFAULT_ROOTS = ["~/oral/jobs", "/Volumes/oral/jobs", "D:/oral/jobs", "E:/oral/jobs"]
STAGE_ORDER = ["00-input", "10-tts", "20-edit", "30-render", "40-final"]
STATE_LABEL = {
    "running": "RUN",
    "done": "DONE",
    "failed": "FAIL",
    "blocked": "WAIT",
    "unreadable": "ERR?",
}


def now() -> datetime:
    return datetime.now(timezone.utc)


def parse_ts(value: str | None) -> datetime | None:
    """接受 ISO8601（带 Z / 偏移 / 不带时区）。解析失败返回 None。"""
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
        else:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def fmt_age(seconds: float | None) -> str:
    if seconds is None:
        return "?"
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h"
    return f"{seconds // 86400}d"


def fmt_eta(value) -> str:
    if value is None or value == "":
        return "-"
    try:
        seconds = int(float(value))
    except (TypeError, ValueError):
        return str(value)[:10]
    if seconds <= 0:
        return "-"
    if seconds < 60:
        return f"~{seconds}s"
    if seconds < 3600:
        return f"~{seconds // 60}m"
    return f"~{seconds / 3600:.1f}h"


def read_last_event(meta_dir: str) -> dict | None:
    path = os.path.join(meta_dir, "events.jsonl")
    if not os.path.isfile(path):
        return None
    last = None
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    last = json.loads(line)
                except json.JSONDecodeError:
                    continue
    except OSError:
        return None
    return last


def parse_handoff_next(meta_dir: str) -> str:
    path = os.path.join(meta_dir, "handoff.md")
    if not os.path.isfile(path):
        return ""
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            for line in handle:
                text = line.strip().lstrip("-* ").strip()
                for prefix in ("下一步：", "下一步:", "Next:", "next:"):
                    if text.startswith(prefix):
                        return text[len(prefix):].strip()
    except OSError:
        return ""
    return ""


def load_jobs(roots: list[str]) -> tuple[list[dict], list[str]]:
    jobs: list[dict] = []
    seen: set[str] = set()
    missing: list[str] = []
    for root in roots:
        root = os.path.expanduser(root)
        if not os.path.isdir(root):
            missing.append(root)
            continue
        try:
            names = sorted(os.listdir(root))
        except OSError as exc:
            missing.append(f"{root} ({exc})")
            continue
        for name in names:
            if name.startswith("."):
                continue
            meta = os.path.join(root, name, "90-meta")
            status_path = os.path.join(meta, "status.json")
            if not os.path.isfile(status_path):
                continue
            key = f"{root}/{name}"
            if key in seen:
                continue
            seen.add(key)
            try:
                with open(status_path, encoding="utf-8") as handle:
                    data = json.load(handle)
                if not isinstance(data, dict):
                    raise ValueError("status.json 不是对象")
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                data = {"job": name, "state": "unreadable", "error": str(exc)}
            data.setdefault("job", name)
            data["_root"] = root
            data["_dir"] = os.path.join(root, name)
            updated = parse_ts(data.get("updated_at"))
            if updated is None:
                try:
                    updated = datetime.fromtimestamp(os.path.getmtime(status_path), timezone.utc)
                except OSError:
                    updated = None
            data["_updated"] = updated
            data["_age"] = (now() - updated).total_seconds() if updated else None
            data["_last_event"] = read_last_event(meta)
            if not data.get("next"):
                data["next"] = parse_handoff_next(meta)
            jobs.append(data)
    return jobs, missing


def decorate(jobs: list[dict], stale_after: float) -> None:
    for job in jobs:
        state = str(job.get("state") or "").lower()
        if state == "running" and job.get("_age") is not None and job["_age"] > stale_after:
            job["_display"] = "STALE"
        else:
            job["_display"] = STATE_LABEL.get(state, (state or "?").upper()[:5])


def sort_key(job: dict):
    rank = {"failed": 0, "blocked": 1, "running": 2, "done": 3, "unreadable": 4}
    return (rank.get(str(job.get("state")).lower(), 5), -(job.get("_age") or 0))


def truncate(text: str, width: int) -> str:
    text = str(text or "")
    return text if len(text) <= width else text[: max(0, width - 1)] + "…"


def render_table(jobs: list[dict]) -> str:
    if not jobs:
        return "（没有找到任何 job：确认共享盘已挂载，或 --root 指向 jobs 目录）"
    headers = ["JOB", "STAGE", "STATE", "PCT", "AGE", "OWNER", "ETA", "NEXT"]
    rows = []
    for job in jobs:
        pct = job.get("percent")
        pct_text = "-" if pct is None else f"{int(float(pct))}%"
        rows.append([
            truncate(job.get("job", "?"), 26),
            truncate(job.get("stage", "-"), 10),
            job.get("_display", "-"),
            pct_text,
            fmt_age(job.get("_age")),
            truncate(job.get("owner", "-"), 4),
            fmt_eta(job.get("eta_s")),
            truncate(job.get("next") or job.get("step") or "", 34),
        ])
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers)).rstrip()
    out = [line, "  ".join("-" * widths[i] for i in range(len(headers)))]
    for row in rows:
        out.append("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)).rstrip())
    counts: dict[str, int] = {}
    for job in jobs:
        key = job.get("_display", "?")
        counts[key] = counts.get(key, 0) + 1
    summary = " · ".join(f"{k} {v}" for k, v in sorted(counts.items()))
    out.append("")
    out.append(summary)
    return "\n".join(out)


def human_detail(job: dict, verbose: bool) -> str:
    lines = [f"== {job.get('job')}  [{job.get('stage', '-')}]  {job.get('_display')}"]
    if job.get("step"):
        lines.append(f"   进度: {job.get('step')}  {job.get('percent', '-')}%")
    if job.get("message"):
        lines.append(f"   消息: {job.get('message')}")
    if job.get("error"):
        lines.append(f"   错误: {job.get('error')}")
    if job.get("next"):
        lines.append(f"   下一步: {job.get('next')}")
    if job.get("_age") is not None:
        lines.append(f"   心跳: {fmt_age(job['_age'])} 前 · owner={job.get('owner', '-')} · ETA {fmt_eta(job.get('eta_s'))}")
    event = job.get("_last_event")
    if event and verbose:
        lines.append(f"   最近事件: {event.get('ts', '')} {event.get('stage', '')} {event.get('event', '')} {event.get('detail', '')}".rstrip())
    return "\n".join(lines)


def emit_json(jobs: list[dict]) -> None:
    clean = []
    for job in jobs:
        item = {k: v for k, v in job.items() if not k.startswith("_")}
        item["display_state"] = job.get("_display")
        item["age_s"] = None if job.get("_age") is None else int(job["_age"])
        item["dir"] = job.get("_dir")
        event = job.get("_last_event")
        item["last_event"] = event
        clean.append(item)
    print(json.dumps(clean, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description="口播任务看板")
    parser.add_argument("--root", action="append", default=[], help="job 根目录，可重复")
    parser.add_argument("--watch", type=float, default=0, help="每 N 秒刷新")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--hide-done", action="store_true", help="不显示已完成")
    parser.add_argument("--stale", type=float, default=30.0, help="心跳超时秒数（默认 30）")
    parser.add_argument("--detail", action="store_true", help="逐 job 显示详情")
    args = parser.parse_args()

    roots = args.root or [os.path.expanduser(p) for p in DEFAULT_ROOTS]
    roots = [r for r in roots if r]
    if not args.watch and not any(os.path.isdir(os.path.expanduser(r)) for r in roots):
        print("找不到 job 根目录：", ", ".join(roots), file=sys.stderr)
        print("提示：先挂载共享盘（/Volumes/oral），或用 --root 指定。", file=sys.stderr)
        return 2

    while True:
        jobs, missing = load_jobs(roots)
        if args.hide_done:
            jobs = [j for j in jobs if str(j.get("state")).lower() != "done"]
        decorate(jobs, args.stale)
        jobs.sort(key=sort_key)
        if args.json:
            emit_json(jobs)
        else:
            if args.watch:
                sys.stdout.write("\033[2J\033[H")
            print(render_table(jobs))
            if missing:
                print("未找到的根：" + ", ".join(missing))
            if args.detail:
                for job in jobs:
                    print()
                    print(human_detail(job, verbose=True))
        sys.stdout.flush()
        if not args.watch:
            break
        try:
            time.sleep(max(1.0, args.watch))
        except KeyboardInterrupt:
            return 0

    failed = any(job.get("_display") in ("FAIL", "STALE", "ERR?") for job in jobs)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
