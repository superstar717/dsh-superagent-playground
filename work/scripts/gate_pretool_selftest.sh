#!/bin/bash
# gate_pretool_selftest.sh — gate_pretool.sh v4（P1 设备授权安全门禁）自测（脚本级，不依赖宿主）
# 覆盖：直接 gh auth login/refresh（含 sudo/bash -c 包裹）拦截；
#       pkill/killall/kill 针对 gh / gh auth（含 pgrep|xargs kill）拦截；
#       原有开工门禁语义不变（非受管目录放行、受管工单目录缺 SCOPE 拦截）。
# P2 重复 PR 预检的测试见 gh-pr-overlap-precheck_selftest.sh。
# 用法：bash ~/.dsh/bin/gate_pretool_selftest.sh
set -u
BIN_DIR="${SELFTEST_BIN:-$HOME/.dsh/bin}"
GATE="$BIN_DIR/gate_pretool.sh"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/gate-selftest.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

pass=0
fail=0

payload() { # payload <command> <cwd> [session]
  python3 - "$1" "$2" "${3:-gate-selftest}" <<'PY'
import json, sys
print(json.dumps({
    "hook_event_name": "PreToolUse",
    "session_id": sys.argv[3],
    "tool_name": "bash",
    "tool_input": {"command": sys.argv[1]},
    "cwd": sys.argv[2],
}, ensure_ascii=False))
PY
}

check() { # check <name> <expected_rc> <command> <cwd>
  local name="$1" expected="$2" cmd="$3" cwd="$4" out rc
  out="$(payload "$cmd" "$cwd" | bash "$GATE" 2>&1)"
  rc=$?
  if [ "$rc" = "$expected" ]; then
    pass=$((pass + 1))
    printf 'ok   %-38s rc=%s\n' "$name" "$rc"
  else
    fail=$((fail + 1))
    printf 'FAIL %-38s expected %s got %s\n     %s\n' "$name" "$expected" "$rc" "$(printf '%s' "$out" | head -3 | tr '\n' ' ')"
  fi
}

# ---------- 基础：非受管目录放行 / 非法 payload fail-closed ----------
check allow-plain                 0 "ls -la /tmp" "/tmp"
check allow-mention-as-text       0 'echo "gh auth refresh 只是文字，不执行"' "/tmp"
out_raw="$(printf 'not-json' | bash "$GATE" 2>&1)"; rc_raw=$?
if [ "$rc_raw" = 2 ]; then
  pass=$((pass + 1)); echo "ok   deny-malformed-payload                     rc=$rc_raw"
else
  fail=$((fail + 1)); echo "FAIL deny-malformed-payload expected 2 got $rc_raw"
fi

# ---------- P1：禁止直接 gh auth login/refresh ----------
check deny-direct-refresh         2 "gh auth refresh -s workflow" "/tmp"
check deny-direct-login           2 "gh auth login -h github.com" "/tmp"
check deny-sudo-login             2 "sudo -u huweixing gh auth login" "/tmp"
check deny-nested-bash-c          2 'bash -c "gh auth refresh -s workflow"' "/tmp"
check allow-wrapper-refresh       0 "$HOME/.dsh/bin/gh-auth-safe.sh refresh -s workflow" "/tmp"
check allow-auth-status           0 "gh auth status" "/tmp"
check allow-auth-switch           0 "gh auth switch -u xingzhe-agent" "/tmp"

# ---------- P1：禁止 pkill/kill 针对 gh auth ----------
check deny-pkill-gh-auth          2 'pkill -f "gh auth refresh"' "/tmp"
check deny-killall-gh             2 "killall gh" "/tmp"
check deny-kill-pgrep             2 'kill $(pgrep -f "gh auth")' "/tmp"
check deny-pgrep-xargs-kill       2 'pgrep -f "gh auth refresh" | xargs kill' "/tmp"
check allow-kill-other-pid        0 "kill 999999" "/tmp"
check allow-pgrep-other           0 "pgrep -f my-service" "/tmp"
check allow-pgrep-own-selftest    0 "pgrep -f gh-auth-safe_selftest | xargs kill" "/tmp"
check allow-cleanup-combo         0 "pkill -f 'for i in 1 2 3'; pgrep -f gh-auth-safe_selftest | xargs kill" "/tmp"
check deny-pkill-auth-wrapper     2 'pkill -f "gh-auth-safe.sh"' "/tmp"

# ---------- 原开工门禁：受管工单目录缺 SCOPE 拦截 / 有 SCOPE 放行 ----------
FAKE_WT="$TMP/ticket"
mkdir -p "$FAKE_WT/work" "$TMP/dsh-superagent-playground/.git/worktrees/x"
printf 'gitdir: %s\n' "$TMP/dsh-superagent-playground/.git/worktrees/x" >"$FAKE_WT/.git"
check deny-ticket-no-scope        2 "ls" "$FAKE_WT"
printf '# SCOPE\n做什么\n' >"$FAKE_WT/work/SCOPE.md"
check allow-ticket-with-scope     0 "ls" "$FAKE_WT"

echo "gate_pretool selftest: pass=$pass fail=$fail"
[ "$fail" = 0 ]
