#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kb-responder 路由逻辑回归自测（无网络、无副作用）。

覆盖 2026-11-13 事故（工单 c568a58a9d7e）的三类缺陷，防止改判定/接管逻辑时回归：
1. URL 查询串里的 ? 不得判为问句；真问句仍要判为问句；
2. 工单/调研类祈使动词一律不接；
3. 「线程里是否已有机器人消息」必须扫整条线程——机器人回复出现在当前消息之后
   （工单接单回执的典型形态）也要判为已接管；
4. superagent 优先窗口：新问句延后判定、工单请求立即处理、旧消息不延后。

用法：
    python3 kb-responder-selftest.py        # 全过 exit 0；任一失败 exit 1

接入位置：本机部署门禁 `kb-responder-deploy.sh` 与仓库 CI
`.github/workflows/kb-responder-selftest.yml`（改动 work/scripts/kb-responder.py 时跑同一份）。
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "kb-responder.py"


def load():
    spec = importlib.util.spec_from_file_location("kb_responder_under_test", TARGET)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise SystemExit(f"无法加载被测脚本：{TARGET}")
    spec.loader.exec_module(module)
    return module


m = load()
failures: list[str] = []


def check(name: str, got, want) -> None:
    ok = got == want
    print(("PASS" if ok else "FAIL"), name, "->", got, "want", want)
    if not ok:
        failures.append(name)


# ── 1. 问句判定 ─────────────────────────────────────────────────────────────
check("URL 查询串 + 调研类请求 → 不是问句",
      m.is_question("https://zhuanlan.zhihu.com/p/1?utm_psn=x 调研一下"), False)
check("链接 + 真问号问句 → 是问句",
      m.is_question("看看这个视频 https://example.com/a?b=1 讲了什么？"), True)
check("普通真问句 → 是问句", m.is_question("姜胡说讲过哪些关于认知的方法？"), True)
check("工单动词 帮我写 → 不接", m.is_question("帮我写一份本周复盘"), False)
check("工单动词 评估 → 不接", m.is_question("评估一下这个方案的可行性"), False)
check("工单动词 总结 → 不接", m.is_question("总结一下姜胡说的内容框架"), False)
check("过短文本 → 不接", m.is_question("好的"), False)
check("WORK_RE 覆盖「调研」", bool(m.WORK_RE.search("调研一下")), True)

# ── 2. 检索 query 清洗 ──────────────────────────────────────────────────────
check("clean_query 剥 URL", m.clean_query("https://a.com/p?x=1 调研一下"), "调研一下")
check("clean_query 剥 @占位", m.clean_query("@_user_1 什么是副业"), "什么是副业")

# ── 3. 线程接管检测（monkeypatch，不访问飞书）──────────────────────────────
def thread_case(messages):
    m.lark_messages = lambda args, timeout=60: messages
    return m.thread_has_bot_reply({"message_id": "om_cur", "thread_id": "omt_1"})


user_msg = {"message_id": "om_cur", "sender": {"sender_type": "user"}}
bot_msg = {"message_id": "om_ack", "sender": {"sender_type": "app"}}
check("线程只有用户消息 → 未接管", thread_case([user_msg]), False)
check("机器人回复在当前消息之后 → 已接管（2026-11-13 回归点）",
      thread_case([user_msg, bot_msg]), True)
check("机器人回复在当前消息之前 → 已接管", thread_case([bot_msg, user_msg]), True)
check("无 thread_id → 未接管", m.thread_has_bot_reply({"message_id": "om_x"}), False)

# ── 4. superagent 优先窗口（用被测模块的 TZ 生成时间，任何时区跑都稳定）─────
now = time.time()
now_local = dt.datetime.now(m.TZ)
fresh = now_local.strftime("%Y-%m-%d %H:%M")
old = (now_local - dt.timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M")


def defer_case(text: str, create_time: str, sender: str = "user", mention: bool = True) -> bool:
    msg = {
        "sender": {"sender_type": sender},
        "mentions": [{"id": m.BOT_OPEN_ID}] if mention else [],
        "create_time": create_time,
        "content": text,
    }
    return m.should_defer(msg, now)


check("新问句 → 延后", defer_case("姜胡说怎么看待副业？", fresh), True)
check("新工单请求 → 不延后", defer_case("调研一下这个项目", fresh), False)
check("旧问句 → 不延后", defer_case("姜胡说怎么看待副业？", old), False)
check("机器人消息 → 不延后", defer_case("姜胡说怎么看待副业？", fresh, sender="app"), False)
check("未 @机器人 → 不延后", defer_case("姜胡说怎么看待副业？", fresh, mention=False), False)

# ── 5. 时间解析（分钟精度）──────────────────────────────────────────────────
age = m.message_age_s({"create_time": fresh}, now)
check("message_age_s 落在当前分钟内", isinstance(age, float) and 0 <= age < 61, True)

print()
if failures:
    print(f"FAILED {len(failures)} 项：{failures}")
    sys.exit(1)
print("ALL PASS")
