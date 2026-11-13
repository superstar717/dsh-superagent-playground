#!/bin/bash
# gh-auth-safe.sh v1.0.0 — gh 设备授权单点入口（LESSONS E132 / 工单 ae3297f806b9 P1）
#
# 为什么：多工单并发跑 `gh auth refresh/login` 时，device code 与轮询会话会互相干扰；
# 用户在 A 流程确认、进程却在「已确认、token 未落盘」窗口被 pkill/kill 清理 →
# GitHub 侧显示已授权，本机 token scopes 不变（E132）。
#
# 本脚本做三件事：
#   1) 串行锁：同一时刻只允许一个设备授权流程；后来者等待（不杀进程），超时明确失败；
#   2) 启动前等待已在跑的 `gh auth login/refresh` 自然结束（绝不 pkill/kill）；
#   3) 授权成功后自动校验：本机 `gh auth status` scopes + GitHub 侧 X-OAuth-Scopes 头，
#      不一致时明确报「可能已授权但 token 未落盘」，要求重新完整走授权。
#
# 用法：
#   gh-auth-safe.sh login   [-h HOST] [-s SCOPE[,SCOPE...]] [其他 gh auth login 参数]
#   gh-auth-safe.sh refresh [-h HOST] [-s SCOPE[,SCOPE...]] [其他 gh auth refresh 参数]
#   gh-auth-safe.sh verify  [-h HOST] [-s SCOPE[,SCOPE...]]   只校验现有凭证，不发起授权
#   gh-auth-safe.sh status                                     显示登录态（不取锁）
#   gh-auth-safe.sh doctor                                     诊断：锁/在跑流程/本机与 GitHub scopes
#   gh-auth-safe.sh help
#
# 环境变量（一般不用改）：
#   GH_AUTH_LOCK_TIMEOUT   等待串行锁的秒数（默认 900）
#   GH_AUTH_PROC_WAIT      等待已存在 gh auth 流程结束的秒数（默认 300）
#   GH_AUTH_DRY_RUN=1      测试用：不真正发起授权，只走锁 + 校验
#   GH_AUTH_DRY_HOLD=N     测试用：持锁停留 N 秒，用于并发串行验证
#
# 设计边界：不杀进程、不改 hooks.json、不代用户完成浏览器确认。
set -u

VERSION="1.0.0"
STATE_DIR="${HOME}/.dsh/state"
LOCK_DIR="${STATE_DIR}/gh-auth.lock"
LOG_FILE="${STATE_DIR}/gh-auth-safe.log"
LOCK_TIMEOUT="${GH_AUTH_LOCK_TIMEOUT:-900}"
PROC_WAIT="${GH_AUTH_PROC_WAIT:-300}"
DRY_RUN="${GH_AUTH_DRY_RUN:-0}"
DRY_HOLD="${GH_AUTH_DRY_HOLD:-0}"

# 锁目录是固定路径；rm -rf 前再核一次，防变量被改坏
[ "$LOCK_DIR" = "$HOME/.dsh/state/gh-auth.lock" ] || {
  echo "gh-auth-safe: 锁路径异常（${LOCK_DIR}），拒绝继续。" >&2
  exit 99
}

log() {
  mkdir -p "$STATE_DIR" 2>/dev/null || true
  printf '%s [pid=%s] %s\n' "$(date '+%F %T')" "$$" "$*" >>"$LOG_FILE" 2>/dev/null || true
}

say() {
  printf '%s\n' "$*" >&2
  log "$*"
}

die() { # die <code> <msg...>
  local code="$1"
  shift
  say "gh-auth-safe: $*"
  exit "$code"
}

file_mtime() { # 便携：macOS(-f %m) / GNU(-c %Y)
  stat -f %m "$1" 2>/dev/null || stat -c %Y "$1" 2>/dev/null || echo 0
}

rotate_log() {
  [ -f "$LOG_FILE" ] || return 0
  local size
  size="$(wc -c <"$LOG_FILE" 2>/dev/null | tr -d ' ' || echo 0)"
  [ -n "$size" ] || size=0
  if [ "$size" -gt 1048576 ]; then
    mv -f "$LOG_FILE" "${LOG_FILE}.1" 2>/dev/null || true
  fi
}

usage() {
  sed -n '20,45p' "$0" | sed 's/^# \{0,1\}//'
}

# ---------- 串行锁 ----------

lock_pid() {
  [ -f "$LOCK_DIR/pid" ] && cat "$LOCK_DIR/pid" 2>/dev/null
}

lock_is_stale() {
  local pid age
  pid="$(lock_pid || true)"
  if [ -z "$pid" ]; then
    # mkdir 与写 pid 之间有极短窗口；给 5 秒宽限，超过视为崩溃残留
    age=$(( $(date +%s) - $(file_mtime "$LOCK_DIR") ))
    [ "$age" -gt 5 ] && return 0 || return 1
  fi
  case "$pid" in
    ''|*[!0-9]*) return 0 ;;
  esac
  kill -0 "$pid" 2>/dev/null && return 1 || return 0
}

release_lock() {
  local pid
  pid="$(lock_pid || true)"
  if [ "$pid" = "$$" ]; then
    rm -rf -- "$LOCK_DIR"
    log "released lock"
  fi
}

acquire_lock() {
  mkdir -p "$STATE_DIR" 2>/dev/null || die 73 "无法创建状态目录 ${STATE_DIR}"
  local start now waited
  start="$(date +%s)"
  while ! mkdir "$LOCK_DIR" 2>/dev/null; do
    if lock_is_stale; then
      say "清理失效锁（持有进程已退出或元数据缺失）：$(lock_pid || echo '无 pid')"
      rm -rf -- "$LOCK_DIR"
      continue
    fi
    now="$(date +%s)"
    waited=$((now - start))
    if [ "$waited" -ge "$LOCK_TIMEOUT" ]; then
      die 75 "等待设备授权串行锁超时（${LOCK_TIMEOUT}s；持有者 pid=$(lock_pid)）。不要杀进程——用 gh-auth-safe.sh doctor 查看，等它自然结束后重试。"
    fi
    if [ $((waited % 10)) -eq 0 ]; then
      say "另一个设备授权流程正在进行（pid=$(lock_pid)），串行等待…已等 ${waited}s（不杀进程）"
    fi
    sleep 2
  done
  printf '%s\n' "$$" >"$LOCK_DIR/pid"
  {
    printf 'pid=%s\n' "$$"
    printf 'started=%s\n' "$(date '+%F %T')"
    printf 'cmd=%s\n' "$*"
  } >"$LOCK_DIR/meta"
  trap release_lock EXIT INT TERM HUP
  log "acquired lock: $*"
}

# ---------- 在跑的 gh auth 流程（只等待，不杀） ----------

running_flows() {
  pgrep -fl 'gh auth (login|refresh)' 2>/dev/null || true
}

wait_running_flows() {
  local start now waited flows
  start="$(date +%s)"
  while :; do
    flows="$(running_flows)"
    [ -z "$flows" ] && return 0
    now="$(date +%s)"
    waited=$((now - start))
    if [ "$waited" -ge "$PROC_WAIT" ]; then
      die 75 "仍有其他 gh auth 流程在运行（不会杀它，GH_AUTH_PROC_WAIT=${PROC_WAIT}s）：${flows}"
    fi
    if [ $((waited % 15)) -eq 0 ]; then
      say "检测到已在运行的 gh auth 流程，等待其自然结束（不杀进程）…已等 ${waited}s"
    fi
    sleep 2
  done
}

# ---------- scope 校验 ----------

split_scopes() { # "a, b,c" -> 每行一个
  printf '%s\n' "$1" | tr ',' ' ' | tr -s ' ' '\n' | sed '/^$/d'
}

requested_scopes() { # 从 gh auth 参数里提取 -s/--scopes
  local i=0 out="" a
  local -a args=("$@")
  while [ "$i" -lt "${#args[@]}" ]; do
    a="${args[$i]}"
    case "$a" in
      --scopes=*) out="$out ${a#--scopes=}" ;;
      -s|--scopes)
        i=$((i + 1))
        [ "$i" -lt "${#args[@]}" ] && out="$out ${args[$i]}"
        ;;
    esac
    i=$((i + 1))
  done
  printf '%s' "$out"
}

host_from_args() {
  local i=0 a
  local -a args=("$@")
  while [ "$i" -lt "${#args[@]}" ]; do
    a="${args[$i]}"
    case "$a" in
      -h|--hostname)
        i=$((i + 1))
        [ "$i" -lt "${#args[@]}" ] && printf '%s' "${args[$i]}" && return 0
        ;;
      --hostname=*) printf '%s' "${a#--hostname=}" && return 0 ;;
    esac
    i=$((i + 1))
  done
  printf '%s' "github.com"
}

# 读本机 keyring 里的 active 账号 scopes；rc: 0 OK / 3 解析失败 / 4 无账号 / 5 状态非 success
local_scopes_for_host() {
  local host="$1"
  gh auth status --json hosts 2>/dev/null | HOST="$host" python3 -c '
import json, os, sys
host = os.environ.get("HOST", "github.com")
try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(3)
accounts = (data.get("hosts") or {}).get(host) or []
active = [a for a in accounts if a.get("active")] or accounts
if not active:
    sys.exit(4)
acct = active[0]
if acct.get("state") != "success":
    sys.exit(5)
print(acct.get("scopes") or "")
'
}

remote_scopes() {
  gh api -i user 2>/dev/null | tr -d '\r' | awk -F': ' 'tolower($1)=="x-oauth-scopes"{ $1=""; sub(/^ /,""); print }' | head -1
}

verify_auth() { # verify_auth <host> <requested-scopes-csv>
  local host="$1" req="$2" scopes="" rc=9 attempt missing="" remote rmissing="" api_login=""
  # 本机 keyring 偶发瞬时读取失败（并发 gh/钥匙串忙，实测出现过一次），重试 3 次再判失败
  for attempt in 1 2 3; do
    scopes="$(local_scopes_for_host "$host")"
    rc=$?
    [ "$rc" -eq 0 ] && break
    [ "$attempt" -lt 3 ] && sleep 1
  done
  log "local status rc=${rc} scopes[${host}]=${scopes:-<none>} (attempt=${attempt})"

  if [ "$rc" -ne 0 ]; then
    # 退化路径：本机 status 读不到时，用 API 判定 token 是否真的可用，并用 GitHub 侧 scope 头兜底
    api_login="$(gh api user --jq .login 2>/dev/null)"
    if [ -n "$api_login" ]; then
      remote="$(remote_scopes)"
      rmissing=""
      for s in $(split_scopes "$req"); do
        case ", ${remote}, " in
          *", ${s}, "*) ;;
          *) rmissing="${rmissing} ${s}" ;;
        esac
      done
      if [ -n "$rmissing" ]; then
        die 3 "本机 gh auth status 读取失败（rc=${rc}，重试 3 次）；GitHub 侧 token scopes 也缺少：${rmissing# }（GitHub 返回：${remote:-unknown}）。不要杀进程，重新完整走一次：gh-auth-safe.sh refresh -s ${rmissing# }"
      fi
      say "注意：本机 gh auth status 瞬时读取失败（rc=${rc}，重试 3 次），但 API 可用（login=${api_login}），GitHub 侧 scopes=${remote:-<无头>} 已满足要求；按通过处理。"
      say "授权校验通过（API 兜底）：${host} login=${api_login}${req:+；要求包含：${req}}"
      return 0
    fi
    case "$rc" in
      3) die 3 "无法从 gh auth status --json 读取登录态（解析失败，重试 3 次），且 API 调用失败。请人工执行 gh auth status 复核。" ;;
      4) die 3 "${host} 没有已登录账号，且 API 调用失败。请执行：gh-auth-safe.sh login -h ${host}" ;;
      5) die 3 "${host} 账号状态非 success（token 无效/过期），且 API 调用失败。请执行：gh-auth-safe.sh login -h ${host}" ;;
      *) die 3 "读取本机 scopes 失败（rc=${rc}），且 API 调用失败。" ;;
    esac
  fi

  if [ -n "$req" ]; then
    for s in $(split_scopes "$req"); do
      case ", ${scopes}, " in
        *", ${s}, "*) ;;
        *) missing="${missing} ${s}" ;;
      esac
    done
    if [ -n "$missing" ]; then
      die 3 "本机 token scopes 缺少：${missing# }（当前：${scopes:-none}）。GitHub 侧可能已授权但 token 未落盘——不要杀进程，重新完整执行：gh-auth-safe.sh refresh -s ${missing# }"
    fi
  fi

  # GitHub 侧核对：OAuth token 的 X-OAuth-Scopes 头（细粒度 token 无此头则跳过）
  remote="$(remote_scopes)"
  if [ -n "$remote" ]; then
    if [ -n "$req" ]; then
      for s in $(split_scopes "$req"); do
        case ", ${remote}, " in
          *", ${s}, "*) ;;
          *) rmissing="${rmissing} ${s}" ;;
        esac
      done
    fi
    if [ -n "$rmissing" ]; then
      die 3 "GitHub 侧 token scopes 缺少：${rmissing# }（GitHub 返回：${remote}；本机：${scopes}）。这通常意味着授权未落盘；不要杀进程，重新完整走一次：gh-auth-safe.sh refresh -s ${rmissing# }"
    fi
    log "remote scopes[${host}]=${remote}"
  else
    say "提示：未取到 GitHub 侧 X-OAuth-Scopes 头（细粒度 token 或网络异常），已按本机 scopes 判定通过。"
  fi

  say "授权校验通过：${host} scopes=${scopes:-none}${req:+；要求包含：${req}}"
}

# ---------- 子命令 ----------

do_auth() { # do_auth <login|refresh> <gh auth args...>
  local kind="$1"
  shift
  local host req rc
  host="$(host_from_args "$@")"
  req="$(requested_scopes "$@")"
  rotate_log
  acquire_lock "$kind $*"
  wait_running_flows

  if [ "$DRY_RUN" = "1" ]; then
    say "DRY_RUN：跳过真实 gh auth ${kind}（不发起设备流），仅走锁 + 校验现有凭证"
    [ "$DRY_HOLD" -gt 0 ] && sleep "$DRY_HOLD"
    verify_auth "$host" "$req"
    exit 0
  fi

  say "开始 gh auth ${kind}（单点锁已持有）。若出现设备码，请只在本人浏览器完成确认；完成前不要杀进程。"
  gh auth "$kind" "$@"
  rc=$?
  log "gh auth ${kind} rc=${rc}"

  if [ "$rc" -ne 0 ]; then
    say "gh auth ${kind} 未成功（rc=${rc}）。不要清理进程；稍后用 gh-auth-safe.sh status 复核，必要时重新完整执行。"
    exit "$rc"
  fi

  verify_auth "$host" "$req"
}

cmd_verify() {
  rotate_log
  local host req
  host="$(host_from_args "$@")"
  req="$(requested_scopes "$@")"
  verify_auth "$host" "$req"
}

cmd_status() {
  local attempt rc=0
  for attempt in 1 2 3; do
    if gh auth status; then
      log "status ok (attempt=${attempt})"
      return 0
    fi
    rc=$?
    [ "$attempt" -lt 3 ] && sleep 1
  done
  die 1 "gh auth status 失败（重试 3 次：未登录、token 无效或钥匙串瞬时不可读，rc=${rc}）。"
}

cmd_doctor() {
  echo "== gh-auth-safe v${VERSION} =="
  echo "锁目录：${LOCK_DIR}"
  if [ -d "$LOCK_DIR" ]; then
    echo "  状态：存在（持有者 pid=$(lock_pid || echo '未知')）"
    [ -f "$LOCK_DIR/meta" ] && sed 's/^/  /' "$LOCK_DIR/meta"
  else
    echo "  状态：无（空闲）"
  fi
  echo "在跑的 gh auth 流程（只等待、不杀）："
  local flows
  flows="$(running_flows)"
  if [ -n "$flows" ]; then
    printf '%s\n' "$flows" | sed 's/^/  /'
  else
    echo "  无"
  fi
  echo "本机登录态："
  gh auth status 2>&1 | sed 's/^/  /' || true
  echo "GitHub 侧 scope 头："
  local remote
  remote="$(gh api -i user 2>/dev/null | tr -d '\r' | awk -F': ' 'tolower($1)=="x-oauth-scopes"{ $1=""; sub(/^ /,""); print }' | head -1)"
  echo "  ${remote:-<未取到>}"
  echo "最近日志：${LOG_FILE}"
  [ -f "$LOG_FILE" ] && tail -n 5 "$LOG_FILE" | sed 's/^/  /'
}

case "${1:-}" in
  login|refresh)
    kind="$1"
    shift
    do_auth "$kind" "$@"
    ;;
  verify)
    shift
    cmd_verify "$@"
    ;;
  status)
    shift
    cmd_status "$@"
    ;;
  doctor)
    shift
    cmd_doctor "$@"
    ;;
  help|-h|--help|"")
    usage
    ;;
  *)
    die 64 "未知子命令：$1（用 gh-auth-safe.sh help 查看用法）"
    ;;
esac
