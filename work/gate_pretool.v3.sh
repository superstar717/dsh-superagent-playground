#!/bin/bash
# gate_pretool.sh v3 — PreToolUse(Bash) 开工门禁（fail-closed）
# v2→v3 变更 2026-11-11（活跃目录纳管，工单 5bad87c3b81b，方案：工单目录 work/方案-活跃目录纳管.md，用户已确认）：
#   管辖扩展：superagent 工单工作区纳管——目录 .git 为指针文件且指向 */dsh-superagent-playground/.git/worktrees/*
#   （executor.prepare 的真实产物签名）。清单语义=非空 work/SCOPE.md（轻量 scope ack，非研究三定）；
#   .gate_exempt 按目录退出保留。只拦 Bash，Edit/Write 不拦（保证可写 SCOPE.md 自举）。
#   研究项目（reusable/CHECKLIST.md 或 work/TODO_开工.md）语义与优先级不变（更严者先）。
# v2 修复记录 2026-10-28（审查报告 work/codex_review.md，详见 .bak-v2 对照）：
#   C1  阻断协议统一为 exit 2 + stderr 理由（stdout JSON 不被解析，不再输出）
#   A1  stdin 只读一次（DSH payload 顶层总带 cwd）
#   A3  只统计「三定」section 的未勾项；9问/体检/交付不参与（修复 N2 循环依赖：
#       通用体检本身要读数据，不能作为数据命令前置）
#   N1  同时检查 cwd 与 tool_input.workdir 两端的项目根
#   N5  清单结构校验（缺「三定」节/无条目 = 阻断，不再按 0 项放行）
#   N8  fail-closed：解析/依赖/读取故障一律 exit 2（宿主把 hook 故障视为放行）
#   A4  豁免改为项目根 .gate_exempt 标记文件（不再硬编码路径）
# 管辖范围：①研究项目根（reusable/CHECKLIST.md 或 work/TODO_开工.md）②superagent 工单工作区（playground worktree 指针）。
command -v python3 >/dev/null 2>&1 || {
  echo "开工门禁：缺少 python3，无法验证清单状态。" >&2
  exit 2
}

input=$(cat)
PY=$(cat <<'PYEOF'
import json, re, sys
from pathlib import Path

def deny(msg):
    print("开工门禁：" + msg, file=sys.stderr)
    sys.exit(2)

def managed(root: Path) -> bool:
    return (root / "reusable/CHECKLIST.md").is_file() or (root / "work/TODO_开工.md").is_file()

def is_ticket_workspace(root: Path) -> bool:
    """superagent 工单工作区签名：.git 为指针文件，指向 playground 主仓的 worktrees 管理区。"""
    gitp = root / ".git"
    if not gitp.is_file():
        return False
    try:
        text = gitp.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return "dsh-superagent-playground/.git/worktrees/" in text

def governed(root: Path) -> bool:
    return managed(root) or is_ticket_workspace(root)

def project_root(directory: Path):
    if not directory.is_dir():
        return None
    for root in (directory, *directory.parents):
        if governed(root):
            return root
    return None

def check_gate(root: Path):
    if (root / ".gate_exempt").is_file():
        return
    if managed(root):
        check_research(root)
        return
    if is_ticket_workspace(root):
        scope = root / "work/SCOPE.md"
        if not (scope.is_file() and scope.read_text(encoding="utf-8", errors="replace").strip()):
            deny(
                f"开工门禁（工单目录）：{root} 是 superagent 工单工作区，尚未登记范围。\n"
                "请先用 Write 工具写 work/SCOPE.md（1-3 句：本工单做什么、不做什么），再继续 Bash 操作；"
                "已完结工单目录仅回访时，可在目录根放 .gate_exempt（建议附理由）。"
            )
        return
    # 非受管目录：放行

def check_research(root: Path):
    todo = root / "work/TODO_开工.md"
    if not todo.is_file():
        deny(f"{root} 缺 work/TODO_开工.md。请先运行 newproj 初始化并完成三定。")
    text = todo.read_text(encoding="utf-8", errors="replace")
    in_section, saw_section = False, False
    unchecked = total = 0
    for line in text.splitlines():
        if line.startswith("## "):
            in_section = "三定" in line
            saw_section = saw_section or in_section
            continue
        if not in_section:
            continue
        m = re.match(r"\s*[-*+]\s+\[( |x|X)\]", line)
        if m:
            total += 1
            if m.group(1) == " ":
                unchecked += 1
    if not saw_section or total == 0:
        deny(f"{todo} 缺「三定」节或条目格式无法识别（需 '## 三定' 标题与 '- [ ]' 条目）。")
    plan = root / "work/分析计划.md"
    if unchecked > 0:
        deny(f"三定未完成：{todo} 三定节还有 {unchecked}/{total} 项未勾；书面计划 {plan} 必须先落成（9问/体检/交付按阶段推进，不在此门禁内）。")
    if not (plan.is_file() and plan.read_text(encoding="utf-8", errors="replace").strip()):
        deny(f"三定已勾但 {plan} 缺失或为空。")

try:
    data = json.load(sys.stdin)  # 只读一次
    if (data.get("hook_event_name") or "") != "PreToolUse":
        sys.exit(0)
    args = data.get("tool_input") or {}
    cmd = args.get("command")
    if not isinstance(cmd, str) or not cmd.strip():
        sys.exit(0)
    cwd_s = data.get("cwd") or ""
    cwd = Path(cwd_s) if cwd_s else Path.cwd()
    if not cwd.is_absolute():
        deny("cwd 非绝对路径")
    roots = []
    r0 = project_root(cwd)
    if r0:
        roots.append(r0)
    wd = args.get("workdir")
    if isinstance(wd, str) and wd.strip():
        wdp = Path(wd)
        if not wdp.is_absolute():
            wdp = cwd / wdp
        r1 = project_root(wdp)
        if r1 and r1 not in roots:
            roots.append(r1)
    for root in roots:
        check_gate(root)
except SystemExit:
    raise
except Exception as e:
    deny(f"状态读取或解析失败（fail-closed）：{type(e).__name__}: {e}")
sys.exit(0)
PYEOF
)
printf '%s' "$input" | python3 -c "$PY"
rc=$?
case "$rc" in
  0|2) exit "$rc" ;;
  *)
    echo "开工门禁：检查程序异常退出(rc=$rc)。" >&2
    exit 2
    ;;
esac
