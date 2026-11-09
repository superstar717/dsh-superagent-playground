#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kb-monthly-feedforward — 月报一个数：本月被创作实际引用（反哺）的旧笔记数。

「反哺创作次数」= impact_log 中本月记录的影响条数（每次创作引用一条洞见/旧知识
即一条记录），附 采纳闭环 台账（kb-responder 的 adoption.jsonl）里的采纳/忽略数。

用法：
    python3 kb-monthly-feedforward.py               # 本月
    python3 kb-monthly-feedforward.py --month 2026-11
    python3 kb-monthly-feedforward.py --list        # 列出本月每条反哺记录
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sqlite3
from pathlib import Path

HOME = Path.home()
DB_PATH = HOME / "姜胡说" / "kb_para" / ".kb_para" / "db" / "kb_para.sqlite"
LEDGER = HOME / "姜胡说" / ".kb_responder" / "adoption.jsonl"
TZ = dt.timezone(dt.timedelta(hours=8))


def main() -> int:
    ap = argparse.ArgumentParser(description="月度旧知识反哺创作计数")
    ap.add_argument("--month", default=f"{dt.datetime.now(TZ):%Y-%m}", help="YYYY-MM")
    ap.add_argument("--list", action="store_true", help="逐条列出")
    args = ap.parse_args()
    month = args.month

    if not DB_PATH.exists():
        print(f"db not found: {DB_PATH}")
        return 1
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "SELECT insight_id, work_title, work_kind, logged_at FROM impact_log "
            "WHERE logged_at LIKE ? ORDER BY logged_at", (f"{month}%",)
        ).fetchall()
        fed = conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE source_type='insight' AND created_at LIKE ?",
            (f"{month}%",),
        ).fetchone()[0]
    finally:
        conn.close()

    # 采纳台账（闭环链路：推送→采纳→写回+待办）
    adopted = ignored = 0
    if LEDGER.exists():
        for line in LEDGER.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if not r.get("ts", "").startswith(month):
                continue
            if r.get("action") == "adopt":
                adopted += 1
            elif r.get("action") == "ignore":
                ignored += 1

    print(f"月度反哺报告 {month}")
    print(f"  创作实际引用旧知识（impact）: {len(rows)} 次")
    print(f"  洞见写回常青笔记（writeback 节点新增）: {fed} 条")
    print(f"  飞书推送采纳 {adopted} / 忽略 {ignored}")
    if args.list:
        for iid, title, kind, at in rows:
            print(f"  - [{at[:16]}] {iid} → {title} ({kind or '未分类'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
