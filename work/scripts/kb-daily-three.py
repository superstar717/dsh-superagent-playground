#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每日三洞见 — kb_para 第二大脑的每日投递任务。

从洞见库（validated + candidate）中按日期轮换选出 3 条，
写归档文件到 kb_para/daily/，并推送到飞书（失败回退 macOS 本地通知）。

设计约定（2026-11-06 挽救行动）：
- 只读洞见库 sqlite，不写库、不改变引擎状态（与 auto-insight 各司其职）。
- 轮换确定性：同一天重复运行选出的 3 条不变；每天换一批（3 条/天，整库轮完一轮约 n/3 天）。
- 同日防重：归档文件已存在即跳过（--force 可强制重跑）。
- 投递失败不丢内容：归档文件始终先落盘，飞书失败回退 osascript 通知。

用法：
    python3 kb-daily-three.py                 # 常规运行（launchd 每日调用）
    python3 kb-daily-three.py --force         # 忽略同日防重
    python3 kb-daily-three.py --dry-run       # 只打印不写档不发送

环境变量：
    KB_PROJECT_ROOT    默认 ~/姜胡说/kb_para
    KB_FEISHU_CHAT_ID  默认 oc_cdc85cf09ef6e751a51da9bc6d19c2fb（openclaw助手 对话）
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(
    os.environ.get("KB_PROJECT_ROOT", str(Path.home() / "姜胡说" / "kb_para"))
).expanduser()
DB_PATH = PROJECT_ROOT / ".kb_para" / "db" / "kb_para.sqlite"
DAILY_DIR = PROJECT_ROOT / "daily"
LOG_FILE = Path.home() / "姜胡说" / "logs" / "kb-daily-three.log"
CHAT_ID = os.environ.get("KB_FEISHU_CHAT_ID", "oc_cdc85cf09ef6e751a51da9bc6d19c2fb")
LARK_CANDIDATES = [
    Path.home() / ".local" / "bin" / "lark-bot",
    Path.home() / ".dsh" / "state" / "superagent" / "worker-bin" / "lark-cli",
]
N_PICK = 3


def log(msg: str) -> None:
    line = f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def one_line(text: str, limit: int = 110) -> str:
    t = re.sub(r"\s+", " ", (text or "").strip())
    return t if len(t) <= limit else t[: limit - 1] + "…"


def load_insights() -> list[dict]:
    """validated 优先，其后按 confidence 降序；同日内顺序稳定。"""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            """
            SELECT id, title, observation, connection, hypothesis,
                   potential_value, confidence, status
            FROM insights
            WHERE status IN ('validated', 'candidate')
            ORDER BY CASE status WHEN 'validated' THEN 0 ELSE 1 END,
                     confidence DESC, id ASC
            """
        ).fetchall()
    finally:
        conn.close()
    keys = ("id", "title", "observation", "connection", "hypothesis",
            "potential_value", "confidence", "status")
    return [dict(zip(keys, r)) for r in rows]


def pick_of_day(insights: list[dict], day: dt.date) -> list[dict]:
    n = len(insights)
    if n == 0:
        return []
    start = ((day.toordinal() * N_PICK) % n) // 1
    return [insights[(start + i) % n] for i in range(min(N_PICK, n))]


def render(picks: list[dict], day: dt.date, total: int, full: bool) -> str:
    lines = [f"# 🧠 每日三洞见 · {day:%Y-%m-%d}", ""]
    if not picks:
        lines += ["洞见库中暂无可用洞见（validated/candidate 均为空）。", ""]
    for i, p in enumerate(picks, 1):
        badge = "✅已验证" if p["status"] == "validated" else "💡候选"
        lines.append(f"**{i}. {p['title']}**")
        lines.append(f"　{p['id']} · {badge} · 置信度 {p['confidence']}")
        lines.append(f"- 观察：{one_line(p['observation'])}")
        lines.append(f"- 假设：{one_line(p['hypothesis'])}")
        if full:
            lines.append(f"- 连接：{one_line(p['connection'], 160)}")
            lines.append(f"- 价值：{one_line(p['potential_value'], 160)}")
            lines.append(f"- 新颖性：{one_line(p.get('novelty', ''), 160)}")
        lines.append("")
    tail = (
        f"— 来源：kb_para 洞见库（{total} 条可用，每天轮换 3 条）\n"
        f"— 归档：{DAILY_DIR / (f'{day:%Y-%m-%d}-每日三洞见.md')}"
    )
    lines.append(tail)
    return "\n".join(lines)


def send_feishu(md_text: str) -> tuple[bool, str]:
    lark = next((p for p in LARK_CANDIDATES if p.exists()), None)
    if lark is None:
        return False, "lark-cli not found"
    try:
        proc = subprocess.run(
            [str(lark), "im", "+messages-send", "--chat-id", CHAT_ID, "--markdown", md_text],
            capture_output=True, text=True, timeout=90,
        )
        out = proc.stdout or proc.stderr
        try:
            ok = bool(json.loads(out).get("ok"))
        except (ValueError, TypeError):
            ok = proc.returncode == 0
        return ok, out.strip()[:500]
    except subprocess.TimeoutExpired:
        return False, "lark-cli timeout"
    except OSError as e:
        return False, str(e)


def notify_local(title: str, body: str) -> None:
    script = f'display notification "{body}" with title "{title}" sound name "Glass"'
    try:
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        pass


def main() -> int:
    ap = argparse.ArgumentParser(description="每日三洞见 digest")
    ap.add_argument("--force", action="store_true", help="忽略同日防重")
    ap.add_argument("--dry-run", action="store_true", help="只打印，不写档不发送")
    args = ap.parse_args()

    if not DB_PATH.exists():
        log(f"FAIL db not found: {DB_PATH}")
        return 1

    day = dt.date.today()
    archive = DAILY_DIR / f"{day:%Y-%m-%d}-每日三洞见.md"
    # 同日防重改为「已生成且已推送」才跳过（2026-11-10）：只生成未推送的走补发，
    # 逻辑后移到发送段；--force 仍可强制重新生成。
    if archive.exists() and archive.with_suffix(".md.sent").exists() \
            and not args.force and not args.dry_run:
        log(f"SKIP 今日已生成且已推送: {archive}")
        return 0
    if archive.exists() and args.force and not args.dry_run:
        log(f"--force 重新生成并推送: {archive}")

    insights = load_insights()
    picks = pick_of_day(insights, day)
    msg = render(picks, day, len(insights), full=False)
    full_md = render(picks, day, len(insights), full=True)

    if args.dry_run:
        print(full_md)
        return 0

    # 飞书发送失败重试（2026-11-10）：归档先行、发送后置——旧行为是发送失败仅
    # 本地通知，而同日防重会让后续运行直接 SKIP，当天推送就此永久丢失
    # （11-08/11-09 两天即因瞬时网络故障 EOF/DNS 如此丢失）。
    # 现约定：待发文本落 .msg 旁车文件；发送成功盖 .sent 标记；
    # 归档在但未 .sent → 每次运行补发一次（旁车缺失则发归档全文），超 7 天放弃。
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    msg_path = archive.with_suffix(".md.msg")
    sent_path = archive.with_suffix(".md.sent")
    if archive.exists() and not args.force:
        if sent_path.exists():
            log(f"SKIP 今日已生成且已推送: {archive}")
            return 0
        if msg_path.exists():
            retry_text = msg_path.read_text(encoding="utf-8")
        elif (dt.date.today() - dt.date.fromisoformat(archive.name[:10])).days > 7:
            log(f"GIVE UP 补发超期: {archive}")
            return 0
        else:
            retry_text = archive.read_text(encoding="utf-8")
        log(f"RETRY 推送 {archive.name}（此前发送失败）")
        ok, detail = send_feishu(retry_text)
        if ok:
            sent_path.write_text(dt.datetime.now().isoformat(), encoding="utf-8")
            log("SENT feishu ✓（补发成功）")
        else:
            log(f"FEISHU FAILED（补发仍失败，下次运行再试）. detail: {detail}")
            notify_local("每日三洞见", "飞书推送补发仍失败（见归档文件，将自动再试）")
        return 0

    archive.write_text(full_md, encoding="utf-8")
    msg_path.write_text(msg, encoding="utf-8")
    log(f"WROTE {archive} ({len(picks)}/3 picks, pool={len(insights)})")

    ok, detail = send_feishu(msg)
    if ok:
        sent_path.write_text(dt.datetime.now().isoformat(), encoding="utf-8")
        log("SENT feishu ✓")
    else:
        log(f"FEISHU FAILED → local notification（归档已留，下次运行自动补发）. detail: {detail}")
        notify_local("每日三洞见", "今日 3 条洞见已生成（飞书推送失败，将自动补发）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
