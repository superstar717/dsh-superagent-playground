#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kb-responder — 飞书群「superagent 优先」的图谱问答兜底（①）+ 洞见采纳/忽略闭环（②）。

① 问答分支（2026-11-13 改为 superagent 优先、图谱兜底）：
   DSH superagent 是该群 @机器人 消息的主处理方（工单/接单回执/结果都在同一线程）。
   本进程只在一条候选问句经过 QA_GRACE_S 秒、且线程内仍无任何机器人消息时，
   才调用 GraphMind /search 兜底回答；回复带「**【图谱问答·兜底】**」标记，
   让群里一眼能分清归属。含工单/调研等祈使动词的消息永不接，直接留给工单流。
   缘起（工单 c568a58a9d7e，2026-11-13）：知乎链接查询串里的 "?" 曾被当成问号，
   把「调研一下」误判为问句交给图谱回答（GraphMind 无联网能力，答案无用），
   又与 superagent 的工单答复重复；用户明确「这应该交给 superagent 处理」。
   同时修复线程守卫：原实现只扫当前消息之前的回复，根消息会立刻 break，
   检测不到 superagent 在同一线程里的接单回执。

② 洞见闭环：回复「每日三洞见」推送「采纳N/忽略N」→ kb validate --accept +
   kb writeback 写回常青笔记 + 进创作待办（dtodo work 轨），并记采纳台账。

设计约定：
- 轮询 lark-cli 消息列表，不订阅 im.message.receive_v1 事件总线——
  DSH superagent 已持有该 EventKey 的唯一消费者，多挂消费者可能抢事件，
  会影响工单管线；轮询完全旁挂，零干扰。
- superagent 优先：候选问句先等 QA_GRACE_S（60s）再判定；判定时线程里只要有
  任何机器人消息（含接单回执/结果），本进程就不插话。兜底只是兜底，不是主路径。
- 确定性匹配：只接「@机器人 + 问句形态」的消息；URL 里的 ? 不算问号；含
  工单/调研等祈使动词一律不接（留给 DSH 工单流），两可时不接。洞见采纳只认
  回复推送 的线程内「采纳N/忽略N」格式。
- 幂等：message_id 去重（state.json），轮询重叠窗口不重复处理。
- 失败不悬空：查询失败回一条简短告知；采纳链路失败回错误说明。
- 单实例：flock 锁，重复启动直接退出。

用法：
    python3 kb-responder.py                # 常驻（launchd KeepAlive）
    python3 kb-responder.py --once         # 跑一轮轮询退出（调试/测试）
    python3 kb-responder.py --dry-run      # 只打印将执行的动作，不真发消息/不写库
    python3 kb-responder.py --reset-state  # 清空去重状态（丢最近记录，慎用）
    python3 kb-responder.py --inject-top '<消息json>'      # 注入合成顶层消息走同一处理链
    python3 kb-responder.py --inject-reply '<消息json>'    # 注入合成线程回复走同一处理链
"""
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# ── 配置（单点定义） ────────────────────────────────────────────────────────
HOME = Path.home()
CHAT_ID = os.environ.get("KB_FEISHU_CHAT_ID", "oc_cdc85cf09ef6e751a51da9bc6d19c2fb")
BOT_OPEN_ID = os.environ.get("KB_BOT_OPEN_ID", "ou_762928d52aa1a609efe8da2311d19478")
BOT_NAME = "openclaw助手"
GRAPH_BASE = os.environ.get("GRAPHMIND_BASE", "http://127.0.0.1:8777").rstrip("/")
GRAPH_DATASET = os.environ.get("GRAPHMIND_DATASET", "jianghushu-methodology_b0607c")
KB_BIN = os.environ.get("KB_BIN", str(HOME / "姜胡说" / "embed_env" / "bin" / "kb"))
KB_BIN = Path(KB_BIN)
KB_PROJECT_ROOT = Path(os.environ.get(
    "KB_PROJECT_ROOT", str(HOME / "姜胡说" / "kb_para")))
DAILY_DIR = KB_PROJECT_ROOT / "daily"
TODOS_FILE = Path(os.environ.get(
    "KB_TODOS_FILE", str(HOME / ".dsh" / "memories" / "TODOS-work.md")))
STATE_DIR = HOME / "姜胡说" / ".kb_responder"
STATE_FILE = STATE_DIR / "state.json"
LEDGER_FILE = STATE_DIR / "adoption.jsonl"
LOCK_FILE = STATE_DIR / "responder.lock"
LOG_FILE = HOME / "姜胡说" / "logs" / "kb-responder.log"
LARK_CANDIDATES = [
    Path.home() / ".local" / "bin" / "lark-bot",
    Path.home() / ".dsh" / "state" / "superagent" / "worker-bin" / "lark-cli",
]
POLL_INTERVAL = int(os.environ.get("KB_RESPONDER_POLL", "20"))
POLL_OVERLAP_S = 180          # 重叠窗口，防轮询间隙漏消息（幂等去重兜底）
PUSH_ACTIVE_DAYS = 7          # 推送注册后跟踪其线程回复的天数
ANSWER_MAX_CHARS = 2800       # 飞书单条上限内；超出截断
SEARCH_TIMEOUT_S = 90
SEEN_CAP = 2000
QA_GRACE_S = 60               # superagent 优先窗口：候选问句先等这么久再判定
TZ = dt.timezone(dt.timedelta(hours=8))

# 问句形态（保守：问号 或 明确疑问开头）；祈使/工单形态一律不接
QUESTION_START_RE = re.compile(
    r"^(问|查|搜|什么是|什么叫|谁(是|有|说过)|哪个|哪些|怎么|怎样|如何|为什么|为啥|"
    r"有没有|讲过|说过|聊过|提过|提到|介绍一下?|说说|解释|区别|关系|对比|总结)"
)
# 工单/调研等祈使动词：出现即判定为「交给 superagent 的任务」，图谱问答永不接。
# 2026-11-13 补入 调研/研究/评估/核实/整理…（此前「调研一下」只因 URL 的 ? 被误判为问句）。
WORK_RE = re.compile(
    r"(工单|开票|剔除|归档|部署|提交|合并|回填|同步|修复|修理|重启|删除|删掉|卸载|"
    r"执行|跑一下|跑一遍|建个|建立|生成|写个|写一份|打印|导出|下载|上传|安装|配置|"
    r"帮忙做|帮我做|帮我写|列个清单|做成|给我做|调研|研究|评估|核实|核对|核查|查证|"
    r"总结|整理|汇总|梳理|分析|对比|改造|接入|上线|爬取|抓取|提取)"
)
URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
ADOPT_RE = re.compile(r"^\s*(采纳|忽略)\s*([1-9])?\s*$")

log = lambda msg: _log(msg)

_NO_SEND = False  # --no-send：真实执行 kb/dtodo 变更，但不向群里发消息（e2e 测试用）


def reply_to(mid: str, text: str, dry: bool) -> tuple[bool, str]:
    """线程回复统一出口：dry / no-send 时只打印。"""
    if dry or _NO_SEND:
        print(f"[no-send] would reply {mid}: {text[:120]}")
        return True, "skipped(no-send)"
    return run_lark(["im", "+messages-reply", "--message-id", mid, "--markdown", text])


def _log(msg: str) -> None:
    line = f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


# ── 状态 ────────────────────────────────────────────────────────────────────
def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"last_poll": 0.0, "seen": [], "pushes": {}}


def save_state(st: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    seen = st.get("seen", [])
    if len(seen) > SEEN_CAP:
        st["seen"] = seen[-SEEN_CAP:]
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, STATE_FILE)


def lark_bin() -> Path | None:
    return next((p for p in LARK_CANDIDATES if p.exists()), None)


def run_lark(args: list[str], timeout: int = 60) -> tuple[bool, str]:
    lb = lark_bin()
    if lb is None:
        return False, "lark-cli not found"
    try:
        proc = subprocess.run([str(lb)] + args, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, "lark-cli timeout"
    except OSError as e:
        return False, str(e)
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode == 0, out.strip()


def lark_messages(args: list[str], timeout: int = 60) -> list[dict]:
    """跑一条消息列表命令，返回消息对象列表（跳过 _diagnostic 等非消息行）。"""
    ok, out = run_lark(args, timeout=timeout)
    if not ok and not out:
        return []
    msgs = []
    for line in out.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if isinstance(d, dict) and d.get("message_id"):
            msgs.append(d)
    return msgs


def iso(epoch: float) -> str:
    return dt.datetime.fromtimestamp(epoch, TZ).strftime("%Y-%m-%dT%H:%M:%S+08:00")


# ── ① 图谱问答 ──────────────────────────────────────────────────────────────
def graph_search(query: str) -> tuple[bool, str]:
    url = f"{GRAPH_BASE}/api/datasets/{GRAPH_DATASET}/search"
    body = json.dumps({"query": query, "mode": "mix"}).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=SEARCH_TIMEOUT_S) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as e:
        return False, f"search error: {e}"
    answer = (data.get("answer") or "").strip()
    # GraphMind 在建索引或 LightRAG 存储锁降级时可能返回字符串 "None"/null：
    # 这不算回答，按失败处理，避免把 "None" 当答案发到群里（2026-11-13 实测）。
    if not answer or answer.lower() in {"none", "null"}:
        return False, "empty answer（GraphMind 可能正在建索引或后端降级）"
    return True, answer


def clean_query(content: str) -> str:
    """去掉 URL、@占位与多余空白后的正文：用于问句判定和检索 query。

    2026-11-13：URL 的查询串（?utm_psn=…）曾让问号判定把「调研一下」误判为问句，
    所以判定与检索都先剥掉 URL。
    """
    t = URL_RE.sub(" ", content or "")
    t = re.sub(r"@_user_\d+", " ", t)
    t = t.replace(f"@{BOT_NAME}", " ")
    return re.sub(r"\s+", " ", t).strip()


def is_question(text: str) -> bool:
    """保守问句判定：URL 里的 ? 不算问号，含工单/调研等祈使动词一律不接。"""
    t = clean_query(text)
    if not (4 <= len(t) <= 200):
        return False
    if WORK_RE.search(t):
        return False
    return ("？" in t or "?" in t) or bool(QUESTION_START_RE.match(t))


def thread_has_bot_reply(msg: dict) -> bool:
    """该消息所在线程里是否已有任何机器人消息（superagent 的接单回执/结果也算）。

    2026-11-13 修复：原实现只扫「当前消息之前」的回复，而且根消息（thread_position=-1）
    在第一条就 break，superagent 在同一线程的答复完全检测不到——这正是知乎调研
    消息被图谱问答重复回答的直接原因。现在扫整条线程，任一条非用户消息即视为已接管。
    """
    tid = msg.get("thread_id")
    if not tid:
        return False
    msgs = lark_messages([
        "im", "+threads-messages-list", "--thread", tid,
        "--order", "asc", "--no-reactions", "--format", "ndjson",
    ], timeout=45)
    return any((m.get("sender") or {}).get("sender_type") != "user" for m in msgs)


def answer_question(msg: dict, qtext: str, dry: bool, init: bool = False) -> None:
    mid = msg.get("message_id", "?")
    query = clean_query(qtext)
    if init:
        log(f"初始化回看，跳过历史问题 {mid}: {query[:50]}")
        return
    if thread_has_bot_reply(msg):
        log(f"忽略（线程内已有机器人回复，superagent 已接管）{mid}: {query[:50]}")
        return
    log(f"Q&A 兜底处理 {mid}: {query[:60]}")
    ok, answer = graph_search(query)
    if not ok:
        log(f"Q&A 查询失败 {mid}: {answer[:120]}")
        reply_text = "【图谱问答·兜底】图谱查询失败（服务超时或暂不可用），请稍后再试。"
        reply_to(mid, reply_text, dry)
        return
    if len(answer) > ANSWER_MAX_CHARS:
        answer = answer[: ANSWER_MAX_CHARS - 60].rstrip() + "\n\n…（内容较长已截断，完整内容见图谱服务）"
    reply_text = (f"**【图谱问答·兜底】** {query}\n\n---\n{answer}"
                  f"\n\n_（superagent 未接管，本次由图谱兜底回答）_")
    ok2, out = reply_to(mid, reply_text, dry)
    log(f"Q&A 兜底回复 {'✓' if ok2 else '✗ ' + out[:200]} {mid}")


# ── ② 洞见闭环 ──────────────────────────────────────────────────────────────
def kb_db_path() -> Path:
    return KB_PROJECT_ROOT / ".kb_para" / "db" / "kb_para.sqlite"


def insight_status(insight_id: str) -> str | None:
    try:
        import sqlite3
        conn = sqlite3.connect(f"file:{kb_db_path()}?mode=ro", uri=True)
        try:
            row = conn.execute("SELECT status FROM insights WHERE id=?", (insight_id,)).fetchone()
        finally:
            conn.close()
        return row[0] if row else None
    except Exception:
        return None


def archive_picks(date_iso: str) -> list[tuple[int, str, str]]:
    """从当日归档解析 [(序号, 标题, INS-id)]。"""
    path = DAILY_DIR / f"{date_iso}-每日三洞见.md"
    try:
        md = path.read_text(encoding="utf-8")
    except OSError:
        return []
    out = []
    for m in re.finditer(r"\*\*([1-9])\.\s*(.+?)\*\*\s*\n\s*(INS-\d+)", md):
        out.append((int(m.group(1)), m.group(2).strip(), m.group(3)))
    return sorted(out)


def append_todo(text: str, dry: bool) -> bool:
    """按 dtodo §条目格式追加一条到 work 轨 TODOS-work.md（tmp+rename 原子写）。"""
    entry_id = f"{int(time.time()) % 0xFFFFFFFF:08x}"
    now = dt.datetime.now(TZ)
    header = (f"[{now:%Y-%m-%d %H:%M}] [id: {entry_id}] [q2] [status: pending] [cat: 创作]")
    block = f"§\n{header}\n{text}\n"
    if dry:
        print(f"[dry] would append todo:\n{block}")
        return True
    try:
        TODOS_FILE.parent.mkdir(parents=True, exist_ok=True)
        old = TODOS_FILE.read_text(encoding="utf-8") if TODOS_FILE.exists() else ""
        if old and not old.endswith("\n"):
            old += "\n"
        tmp = TODOS_FILE.with_suffix(f".tmp.{os.getpid()}")
        tmp.write_text(old + block, encoding="utf-8")
        os.replace(tmp, TODOS_FILE)
        return True
    except OSError as e:
        log(f"dtodo 追加失败: {e}")
        return False


def ledger_append(rec: dict) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        with LEDGER_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass


def run_kb(args: list[str], dry: bool) -> tuple[bool, str]:
    if dry:
        return True, f"[dry] kb {' '.join(args)}"
    if not KB_BIN.exists():
        return False, f"kb not found: {KB_BIN}"
    try:
        proc = subprocess.run(
            [str(KB_BIN)] + args + ["--project-root", str(KB_PROJECT_ROOT)],
            capture_output=True, text=True, timeout=180,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        return False, str(e)
    out = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode == 0, out


def adopt_insight(insight_id: str, title: str, push_date: str, reply_msg: dict, dry: bool) -> None:
    """采纳：validate --accept → writeback → 进创作待办 → 回执 + 台账。"""
    mid = reply_msg.get("message_id", "?")
    status = insight_status(insight_id)
    steps: list[str] = []
    if status != "validated":
        ok, out = run_kb(["validate", insight_id, "--accept"], dry)
        steps.append(f"validate {'✓' if ok else '✗ ' + out[:150]}")
        if not ok:
            _reply_adopt_fail(mid, insight_id, steps, dry)
            return
    ok, out = run_kb(["writeback", insight_id], dry)
    node = ""
    m = re.search(r"Writeback created node:\s*(\S+)", out)
    node = m.group(1) if m else ""
    steps.append(f"writeback {'✓ ' + node if ok else '✗ ' + out[:150]}")
    if not ok:
        _reply_adopt_fail(mid, insight_id, steps, dry)
        return
    todo_text = (f"创作选题（源自洞见 {insight_id}「{title}」，{push_date} 飞书采纳）："
                 f"把该洞见用进一条视频/图文，完成后 kb impact {insight_id} --used-in '<作品名>' 记反哺。")
    ok2 = append_todo(todo_text, dry)
    steps.append(f"todo {'✓' if ok2 else '✗'}")
    ledger_append({
        "ts": dt.datetime.now(TZ).isoformat(), "action": "adopt", "insight": insight_id,
        "title": title, "push_date": push_date, "node": node,
        "by": (reply_msg.get("sender") or {}).get("name", "?"), "message_id": mid,
    })
    reply_text = (f"✅ 已采纳 {insight_id}「{title}」\n"
                  f"已写回常青笔记（{node or '节点见 kb'}）+ 已进创作待办。\n"
                  f"作品完成后可用 `kb impact {insight_id} --used-in <作品名>` 记反哺次数。")
    reply_to(mid, reply_text, dry)
    log(f"采纳完成 {insight_id}: " + "; ".join(steps))


def _reply_adopt_fail(mid: str, insight_id: str, steps: list[str], dry: bool) -> None:
    reply_text = f"⚠️ 采纳 {insight_id} 未完成：{'; '.join(steps)}"
    reply_to(mid, reply_text, dry)
    log(f"采纳失败 {insight_id}: " + "; ".join(steps))


def ignore_insight(insight_id: str, title: str, push_date: str, reply_msg: dict, dry: bool) -> None:
    mid = reply_msg.get("message_id", "?")
    ledger_append({
        "ts": dt.datetime.now(TZ).isoformat(), "action": "ignore", "insight": insight_id,
        "title": title, "push_date": push_date,
        "by": (reply_msg.get("sender") or {}).get("name", "?"), "message_id": mid,
    })
    reply_text = f"已忽略 {insight_id}「{title}」（仅记录，不影响洞见库）。"
    reply_to(mid, reply_text, dry)
    log(f"忽略 {insight_id}")


def process_reply(msg: dict, push_pid: str, push: dict, dry: bool) -> None:
    """推送线程内的回复：采纳N / 忽略N。push 由轮询循环显式给出。"""
    mid = msg.get("message_id", "?")
    sender = msg.get("sender") or {}
    if sender.get("sender_type") != "user" or msg.get("deleted"):
        return
    if mid == push_pid:
        return
    m = ADOPT_RE.match(msg.get("content", ""))
    if not m:
        return
    push_date = push.get("date", "")
    picks = archive_picks(push_date)
    if not picks:
        log(f"归档缺失 {push_date}，无法定位洞见")
        return
    action, n = m.group(1), m.group(2)
    if n is None:
        listing = "\n".join(f"{i}. {t}（{iid}）" for i, t, iid in picks)
        text = f"请指明序号：回复「采纳1/采纳2/采纳3」或「忽略N」。\n{listing}"
        reply_to(mid, text, dry)
        return
    pick = next((p for p in picks if p[0] == int(n)), None)
    if pick is None:
        return
    _, title, insight_id = pick
    if action == "采纳":
        adopt_insight(insight_id, title, push_date, msg, dry)
    else:
        ignore_insight(insight_id, title, push_date, msg, dry)


# ── 轮询主链 ────────────────────────────────────────────────────────────────
def mentions_bot(msg: dict) -> bool:
    return any(mm.get("id") == BOT_OPEN_ID for mm in (msg.get("mentions") or []))


def process_top(msg: dict, st: dict, dry: bool, init: bool = False) -> None:
    mid = msg.get("message_id", "?")
    sender = msg.get("sender") or {}
    content = msg.get("content", "") or ""
    if msg.get("deleted"):
        return
    # 推送注册：机器人发的每日三洞见（顶层消息）
    if sender.get("sender_type") != "user" and "每日三洞见" in content:
        dm = re.search(r"(\d{4}-\d{2}-\d{2})", content)
        st.setdefault("pushes", {})[mid] = {
            "date": dm.group(1) if dm else dt.datetime.now(TZ).strftime("%Y-%m-%d"),
            "added_at": time.time(), "thread_id": msg.get("thread_id", ""),
        }
        log(f"注册推送 {mid} date={st['pushes'][mid]['date']}")
        return
    # ① 问答兜底：人类 + @机器人 + 问句形态（superagent 优先，见 answer_question）
    if sender.get("sender_type") == "user" and mentions_bot(msg):
        qtext = clean_query(content)
        if is_question(qtext):
            answer_question(msg, qtext, dry, init=init)
        else:
            log(f"忽略（非问句/工单请求，留给 superagent）{mid}: {qtext[:50]}")


def message_age_s(msg: dict, now: float) -> float | None:
    """消息创建时刻到 now 的秒数（飞书 create_time 只到分钟，误差 ≤59s）。"""
    raw = msg.get("create_time") or ""
    try:
        ts = dt.datetime.strptime(raw, "%Y-%m-%d %H:%M").replace(tzinfo=TZ).timestamp()
    except ValueError:
        return None
    return now - ts


def should_defer(msg: dict, now: float) -> bool:
    """superagent 优先窗口：新到的候选问句先不处理、不记 seen，下一轮再判定。"""
    sender = msg.get("sender") or {}
    if sender.get("sender_type") != "user" or not mentions_bot(msg):
        return False
    if not is_question(msg.get("content", "") or ""):
        return False
    age = message_age_s(msg, now)
    return age is not None and age < QA_GRACE_S


def poll_once(dry: bool, st: dict) -> None:
    now = time.time()
    start = max(0.0, st.get("last_poll", 0.0) - POLL_OVERLAP_S) if st.get("last_poll") else now - 3600
    end = now
    # 首次启动回看 7 天：注册近期推送（采纳映射需要 push message_id）
    lookback = start if st.get("last_poll") else now - PUSH_ACTIVE_DAYS * 86400
    seen = set(st.get("seen", []))
    init = not st.get("last_poll")  # 首次启动回看：只注册推送，不回答历史问题

    tops = lark_messages([
        "im", "+chat-messages-list", "--chat-id", CHAT_ID,
        "--start", iso(lookback), "--end", iso(end),
        "--order", "asc", "--no-reactions", "--format", "ndjson",
        # 初始化回看翻页（busy 群 7 天远超单页 50 条，漏页会漏注册推送）
        "--page-all", "--page-limit", "10",
    ], timeout=180)
    deferred = st.setdefault("deferred", {})
    st["deferred"] = {k: v for k, v in deferred.items() if now - float(v) < 3600}
    for msg in tops:
        mid = msg.get("message_id")
        if not mid or mid in seen:
            continue
        if should_defer(msg, now):
            if mid not in st["deferred"]:
                st["deferred"][mid] = now
                log(f"延后判定（superagent 优先窗口 {QA_GRACE_S}s）{mid}: "
                    f"{clean_query(msg.get('content', ''))[:50]}")
            continue
        st["deferred"].pop(mid, None)
        seen.add(mid)
        st.setdefault("seen", []).append(mid)
        process_top(msg, st, dry, init=init)

    # 已注册推送的线程回复（②）：按推送逐一解析其线程，回复显式携带推送上下文
    pushes = st.get("pushes", {})
    for pid, p in list(pushes.items()):
        if time.time() - p.get("added_at", 0) > PUSH_ACTIVE_DAYS * 86400 * 2:
            continue
        replies = lark_messages([
            "im", "+threads-messages-list", "--thread", pid,
            "--order", "asc", "--no-reactions", "--format", "ndjson",
        ], timeout=60)
        for msg in replies:
            mid = msg.get("message_id")
            if not mid or mid in seen or mid == pid:
                continue
            seen.add(mid)
            st.setdefault("seen", []).append(mid)
            process_reply(msg, pid, p, dry)

    st["last_poll"] = end
    save_state(st)


def acquire_lock() -> bool:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    fh = LOCK_FILE.open("w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    fh.write(str(os.getpid()))
    fh.flush()
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="kb-responder 图谱问答+洞见闭环")
    ap.add_argument("--once", action="store_true", help="跑一轮轮询退出")
    ap.add_argument("--dry-run", action="store_true", help="只打印动作")
    ap.add_argument("--no-send", action="store_true",
                    help="真实执行 kb/dtodo 变更但不发群消息（e2e 测试）")
    ap.add_argument("--reset-state", action="store_true", help="清空去重状态")
    ap.add_argument("--inject-top", help="注入合成顶层消息 json")
    ap.add_argument("--inject-reply", help="注入合成线程回复 json")
    args = ap.parse_args()

    if args.no_send:
        global _NO_SEND
        _NO_SEND = True

    st = load_state()
    if args.reset_state:
        st = {"last_poll": 0.0, "seen": [], "pushes": {}}
        save_state(st)
        log("state 已清空")

    if args.inject_top or args.inject_reply:
        raw = args.inject_top or args.inject_reply
        msg = json.loads(raw)
        if args.inject_top:
            process_top(msg, st, args.dry_run)
        else:
            tid = msg.get("thread_id", "")
            push_pid, push = next(((k, v) for k, v in st.get("pushes", {}).items()
                                   if k == tid or v.get("thread_id") == tid), (None, None))
            if push is None:
                print("未找到匹配的已注册推送（thread_id 需为推送 message_id 或其线程）")
                return 1
            process_reply(msg, push_pid, push, args.dry_run)
        save_state(st)
        return 0

    if not acquire_lock():
        log("另一实例运行中，退出")
        return 0

    if args.once:
        poll_once(args.dry_run, st)
        return 0

    log(f"kb-responder 启动 poll={POLL_INTERVAL}s chat={CHAT_ID} dataset={GRAPH_DATASET} mode=superagent-first grace={QA_GRACE_S}s")
    while True:
        try:
            poll_once(args.dry_run, st)
        except Exception as e:  # 常驻进程：单轮失败不退出
            log(f"poll 轮异常（继续）: {e!r}")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    sys.exit(main())
