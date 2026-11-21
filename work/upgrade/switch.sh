#!/bin/bash
# Detached DSH host switch with health check and automatic rollback.
# Usage: switch.sh [target-version] [previous-version]
# Runs outside the host (nohup), so it survives the host restart it triggers.
set -u

TARGET="${1:-0.2.2-rc.3}"
PREV="${2:-0.2.1-rc.5}"
STATE="$HOME/.dsh/state"
LOG="$STATE/upgrade-0.2.2.log"
STATUS="$STATE/upgrade-status.json"
CURRENT_LOG="$STATE/dsh-superagent-current.log"
POST_CHECK="$STATE/post-restart-check.txt"
PORT=3082
WORK="$(cd "$(dirname "$0")" && pwd)"

mkdir -p "$STATE"
exec >>"$LOG" 2>&1
echo "=== $(date '+%F %T') switch $PREV -> $TARGET ==="

[ -f "$STATE/superagent.env" ] && . "$STATE/superagent.env"
export PATH="$HOME/.nvm/versions/node/v24.15.0/bin:$HOME/.local/bin:/usr/local/bin:/opt/homebrew/bin:$PATH"

write_status() {
  local status="$1" http="${2:-}" extra="${3:-}"
  python3 - "$STATUS" "$status" "$TARGET" "$PREV" "$http" "$extra" <<'PY'
import json, sys, time
path, status, target, prev, http, extra = sys.argv[1:7]
data = {"status": status, "from": prev, "to": target, "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "http": http, "extra": extra}
with open(path, "w") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
PY
}

http_code() {
  curl -s -o /dev/null -m 3 -w '%{http_code}' "http://127.0.0.1:$PORT/" 2>/dev/null || true
}

stop_host() {
  local pid
  pid="$(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null | head -1)"
  if [ -n "$pid" ]; then
    echo "stopping host pid=$pid"
    kill "$pid" 2>/dev/null || true
    for _ in $(seq 1 25); do kill -0 "$pid" 2>/dev/null || return 0; sleep 1; done
    echo "force killing $pid"
    kill -9 "$pid" 2>/dev/null || true
  else
    echo "no host on :$PORT"
  fi
}

start_host() {
  : >"$CURRENT_LOG"
  nohup dsh --profile superagent --no-open --port "$PORT" >>"$CURRENT_LOG" 2>&1 &
  HOST_PID=$!
  echo "started host pid=$HOST_PID"
}

wait_ready() {
  local code
  for _ in $(seq 1 180); do
    code="$(http_code)"
    if grep -q 'dsh web:' "$CURRENT_LOG" 2>/dev/null && printf '%s' "$code" | grep -qE '^(200|302|401)$'; then
      return 0
    fi
    kill -0 "${HOST_PID:-0}" 2>/dev/null || return 1
    sleep 1
  done
  return 1
}

save_web_url() {
  local url
  url="$(grep -o 'dsh web: http[^ ]*' "$CURRENT_LOG" 2>/dev/null | tail -1 | sed 's/^dsh web: //')"
  [ -n "$url" ] && printf '%s\n' "$url" >"$STATE/web-url"
}

echo "cli on disk: $(dsh --version 2>&1 | head -1)"
write_status "switching" "" "stopping host"

# Let the caller's status report reach the orchestrator before the host dies.
sleep 20

stop_host

if [ "$(dsh --version 2>/dev/null | head -1)" = "$TARGET" ]; then
  echo "target $TARGET already installed; skipping npm install"
else
  echo "installing $TARGET"
  if ! npm i -g "@deepseek-ai/dsh@$TARGET"; then
    echo "install failed; restarting previous version"
    write_status "rolled_back" "" "install failed"
    start_host
    wait_ready && save_web_url || true
    exit 1
  fi
  echo "installed: $(dsh --version 2>&1 | head -1)"
fi

start_host
if wait_ready; then
  code="$(http_code)"
  save_web_url
  echo "ready http=$code"
  write_status "ok" "$code" "switch complete"
  bash "$WORK/post-restart-check.sh" >"$POST_CHECK" 2>&1 || true
  exit 0
fi

echo "new host failed to become ready; rolling back"
tail -40 "$CURRENT_LOG" 2>/dev/null || true
write_status "rolled_back" "$(http_code)" "new host not ready"
stop_host
if npm i -g "@deepseek-ai/dsh@$PREV"; then
  start_host
  if wait_ready; then
    save_web_url
    write_status "rolled_back" "$(http_code)" "rollback host ready"
  else
    write_status "failed" "$(http_code)" "rollback host not ready"
  fi
else
  write_status "failed" "" "rollback install failed"
fi
exit 1
