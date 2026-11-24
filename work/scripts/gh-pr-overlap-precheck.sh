#!/bin/bash
# gh-pr-overlap-precheck.sh — 提 PR 前查 open PR 同文件重叠（P2/E133），警告式，不拦截。
#
# 调用方：~/.local/bin/gh-agent 在 `gh pr create` 前执行（与 gh 命令同一进程环境，
#         因此可以读到登录钥匙串；PreToolUse hook 子进程读不到，见 gate_pretool.sh v4 注释）。
# 输出：有重叠时把警告写到 stderr（随命令输出可见，在 PR 创建之前）；无重叠/失败静默。
# 豁免：命令前加 DSH_PR_OVERLAP_OK=1（本脚本直接放行）。
# 日志：~/.dsh/state/gh-pr-overlap.log（每次判定一行，便于排查）。
set -u
LOG="$HOME/.dsh/state/gh-pr-overlap.log"
mkdir -p "$HOME/.dsh/state" 2>/dev/null || true

if [ "${DSH_PR_OVERLAP_OK:-0}" = "1" ]; then
  printf '%s [skip] DSH_PR_OVERLAP_OK=1\n' "$(date '+%F %T')" >>"$LOG" 2>/dev/null || true
  exit 0
fi

python3 - "$LOG" <<'PY'
import json
import re
import subprocess
import sys
import time

log_path = sys.argv[1]


def log(msg: str) -> None:
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%F %T')} {msg}\n")
    except OSError:
        pass


def run(argv, timeout):
    try:
        p = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except Exception as e:  # 预检失败不阻断
        return 127, "", f"{type(e).__name__}: {e}"


rc, out, _ = run(["git", "rev-parse", "--show-toplevel"], 3)
if rc != 0 or not out.strip():
    log("skip: not a git repo")
    sys.exit(0)
repo = out.strip()

base = None
for cand in ("origin/main", "origin/master", "origin/HEAD"):
    rc, o, _ = run(["git", "-C", repo, "rev-parse", "--verify", "--quiet", cand], 3)
    if rc == 0 and o.strip():
        base = cand
        break
if base is None:
    log(f"skip: no base ref in {repo}")
    sys.exit(0)

rc, out, _ = run(["git", "-C", repo, "diff", "--name-only", f"{base}...HEAD"], 4)
if rc != 0:
    log(f"skip: git diff rc={rc}")
    sys.exit(0)
changed = {line.strip() for line in out.splitlines() if line.strip()}
# 每单必改的簿记文件（SCOPE/复盘/DEPLOY-NOTES/验证记录）不作为重复 PR 证据，避免每个工单 PR
# 都因这些共享路径互报重叠（E133「README、AGENTS 等共享文件易误伤」的同类问题）。
BOOKKEEPING_RE = re.compile(r"^work/(SCOPE\.md|项目复盘\.md|DEPLOY-NOTES\.md|验证记录-[^/]*\.md)$")
changed = {f for f in changed if not BOOKKEEPING_RE.match(f)}
if not changed:
    log(f"ok: no non-bookkeeping changed files vs {base}")
    sys.exit(0)

argv = ["gh", "pr", "list", "--state", "open", "--limit", "50", "--json", "number,title,headRefName,files"]
rc, out, err = run(argv, 8)
if rc != 0:
    log(f"skip: gh pr list rc={rc} {(err or out).strip()[:160]}")
    sys.exit(0)
try:
    prs = json.loads(out)
except Exception:
    log("skip: gh pr list JSON parse failed")
    sys.exit(0)

rc, out, _ = run(["git", "-C", repo, "rev-parse", "--abbrev-ref", "HEAD"], 2)
branch = out.strip() if rc == 0 else ""

overlaps = []
for pr in prs if isinstance(prs, list) else []:
    if not isinstance(pr, dict):
        continue
    if branch and pr.get("headRefName") == branch:
        continue
    files = set()
    for f in pr.get("files") or []:
        if isinstance(f, dict) and f.get("path"):
            files.add(str(f["path"]))
        elif isinstance(f, str):
            files.add(f)
    hit = sorted(files & changed)
    if hit:
        overlaps.append(
            {
                "number": pr.get("number"),
                "title": str(pr.get("title") or ""),
                "files": hit[:8],
            }
        )

if not overlaps:
    log(f"ok: no overlap ({len(changed)} changed files vs {len(prs) if isinstance(prs, list) else 0} open PRs)")
    sys.exit(0)

lines = [
    f"重复 PR 预检（警告，不拦截）：分支 {branch or '?'} 与 {len(overlaps)} 个 open PR 存在同文件重叠："
]
for o in overlaps[:5]:
    lines.append(f"  #{o['number']} {o['title'][:60]} → {', '.join(o['files'])}")
lines.append("确认是否同一机制修复的重复提交；若是请关闭本 PR 并注明以哪份为准（LESSONS E133）。")
lines.append("显式豁免（下次不再提示）：命令前加 DSH_PR_OVERLAP_OK=1。")
print("\n".join(lines), file=sys.stderr)
log(f"warn: {len(overlaps)} overlapping PRs, changed={len(changed)}")
PY
exit 0
