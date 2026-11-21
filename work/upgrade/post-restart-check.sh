#!/bin/bash
# Post-restart health check. Safe to run while the host is up.
# Usage: post-restart-check.sh [--json]
set -u
STATE="$HOME/.dsh/state"
LOG="$STATE/dsh-superagent-current.log"
STATUS="$STATE/upgrade-status.json"
PORT=3082
FAIL=0

say() { printf '%s\n' "$*"; }
check() {
  if "$@" >/dev/null 2>&1; then say "PASS: $*"; else say "FAIL: $*"; FAIL=$((FAIL + 1)); fi
}

say "== DSH upgrade post-restart check $(date '+%F %T')"
say "dsh version: $(dsh --version 2>&1 | head -1)"
[ -f "$STATUS" ] && say "upgrade status: $(tr -d '\n' <"$STATUS")"

if [ -f "$LOG" ]; then
  say "host process: $(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null | head -1)"
  code="$(curl -s -o /dev/null -m 5 -w '%{http_code}' "http://127.0.0.1:$PORT/" 2>/dev/null || true)"
  say "http /: $code"
  case "$code" in 200|302|401) say "PASS: web responds";; *) say "FAIL: web does not respond"; FAIL=$((FAIL + 1));; esac
  say "--- startup warnings/errors (tail 30)"
  grep -iE 'denied|skipped|failed|error|warn' "$LOG" 2>/dev/null | tail -30 || say "(none)"
else
  say "FAIL: missing host log $LOG"
  FAIL=$((FAIL + 1))
fi

say "--- composition check"
if dsh --profile superagent --dump-config >/dev/null 2>"$STATE/dump-config.err"; then
  say "PASS: --dump-config"
else
  say "FAIL: --dump-config ($(tail -3 "$STATE/dump-config.err" 2>/dev/null))"
  FAIL=$((FAIL + 1))
fi

say "--- hooks bridge evidence"
if [ -f /tmp/hook_payload/last.json ]; then
  say "PASS: /tmp/hook_payload/last.json $(stat -f '%Sm' /tmp/hook_payload/last.json 2>/dev/null)"
else
  say "WARN: no /tmp/hook_payload/last.json yet (run a bash tool call, then re-check)"
fi

say "--- superagent state"
if command -v sqlite3 >/dev/null 2>&1; then
  say "sqlite quick_check: $(sqlite3 "$HOME/.dsh/state/superagent-fresh/orchestrator.sqlite" 'pragma quick_check;' 2>&1 | head -1)"
  say "tickets: $(sqlite3 "$HOME/.dsh/state/superagent-fresh/orchestrator.sqlite" 'select count(*) from ticket;' 2>&1 | head -1)"
fi
say "sessions: $(find "$HOME/.dsh/sessions" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')"

say "--- result: $([ "$FAIL" -eq 0 ] && echo OK || echo "$FAIL failure(s)")"
exit "$FAIL"
