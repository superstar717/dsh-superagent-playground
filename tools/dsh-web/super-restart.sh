#!/bin/bash
# super-restart.sh —— 重启 superagent（DSH Web GUI, http://127.0.0.1:3082）
# 用途：新增/更新 DSH 插件、改 profile 配置后，让插件注册生效。
# 环境变量：自动 source ~/.dsh/state/superagent.env（2026-11-08 从运行中进程提取的
#           LLM keys / 代理 / PATH 等 21 项），任何终端、后台、cron 里跑都不丢配置。
#           换了 key 后重新生成：见 README 或 `ps -Eww -p <pid> -o command=` 提取法。
# 重启后的登录链接：会把本次 dsh 进程的 `?token=...` 链接写入 ~/.dsh/state/web-url，
#           并默认用默认浏览器打开（DSH_WEB_OPEN=0 可关闭）。这样重启后无需再从
#           日志里手贴 token。旧标签在同一端口下会复用 30 天会话 cookie，刷新即可。
# 注意：重启会结束当前所有 superagent 会话（对话窗口断开重开，属预期行为）；
#       launchd 定时任务（dysub 等）是独立进程树，不受影响。
# 用法：super-restart.sh [profile]   （缺省 superagent；无需其它参数）
set -e
PROFILE="${1:-superagent}"
CALLER_PORT="${PORT:-}"
CALLER_OPEN="${DSH_WEB_OPEN:-}"
CALLER_OPEN_CMD="${OPEN_CMD:-}"
CALLER_STATE="${DSH_WEB_STATE:-}"

# ---- 环境（self-contained：不依赖你当前 shell 里是否加载了 nvm/keys）----
ENV_FILE="$HOME/.dsh/state/superagent.env"
[ -f "$ENV_FILE" ] && . "$ENV_FILE"
export PATH="$HOME/.nvm/versions/node/v24.15.0/bin:$HOME/.local/bin:/usr/local/bin:/opt/homebrew/bin:$PATH"

# 调用方显式传入的参数优先于环境文件里的同名项
PORT="${CALLER_PORT:-${PORT:-3082}}"
DSH_WEB_OPEN="${CALLER_OPEN:-${DSH_WEB_OPEN:-1}}"
OPEN_CMD="${CALLER_OPEN_CMD:-${OPEN_CMD:-open}}"
STATE_FILE="${CALLER_STATE:-${DSH_WEB_STATE:-$HOME/.dsh/state/web-url}}"

PID=$(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null | head -1)
if [ -n "$PID" ]; then
    echo "停止旧 webserver (pid $PID)..."
    kill "$PID"
    for _ in $(seq 1 15); do
        kill -0 "$PID" 2>/dev/null || break
        sleep 1
    done
    if kill -0 "$PID" 2>/dev/null; then
        echo "  未退出，强制结束"
        kill -9 "$PID" 2>/dev/null || true
    fi
else
    echo "端口 $PORT 上没有运行中的 webserver"
fi

LOG="$HOME/.dsh/state/dsh-$PROFILE-restart.log"
mkdir -p "$HOME/.dsh/state"
echo "启动 dsh --profile $PROFILE --no-open --port $PORT ..."
nohup dsh --profile "$PROFILE" --no-open --port "$PORT" > "$LOG" 2>&1 &
CHILD=$!
echo "已后台启动（约 10-20 秒就绪），等待登录链接..."

# 等就绪行出现并取本次 token 链接（最多 60 秒）；进程提前退出则立即报错
URL=""
for _ in $(seq 1 60); do
    URL="$(grep -o 'dsh web: http[^ ]*' "$LOG" 2>/dev/null | tail -n 1 | sed 's/^dsh web: //' || true)"
    [ -n "$URL" ] && break
    if ! kill -0 "$CHILD" 2>/dev/null; then
        echo "启动进程已退出；请检查日志：$LOG" >&2
        break
    fi
    sleep 1
done

if [ -n "$URL" ]; then
    (umask 077; printf '%s\n' "$URL" > "$STATE_FILE")
    chmod 600 "$STATE_FILE" 2>/dev/null || true
    echo "登录链接已保存：${STATE_FILE}（含凭据，权限 600，勿外传）"
    echo "启动日志：$LOG"
    if [ "$DSH_WEB_OPEN" != "0" ]; then
        if command -v "$OPEN_CMD" >/dev/null 2>&1; then
            if "$OPEN_CMD" "$URL" >/dev/null 2>&1; then
                echo "已在默认浏览器打开登录链接；旧标签刷新即可（同一端口复用 30 天会话）。"
            else
                echo "自动打开失败；可运行 dsh-web-open 重试，或手动打开上面的链接。"
            fi
        else
            echo "未找到打开命令 $OPEN_CMD；可运行 dsh-web-open 取链接。"
        fi
    else
        echo "已跳过自动打开（DSH_WEB_OPEN=0）；需要时运行 dsh-web-open。"
    fi
else
    echo "警告：60 秒内未在 $LOG 找到 dsh web: 登录链接。" >&2
    echo "       请检查启动日志；就绪后可运行 dsh-web-open（会重读日志/状态文件）。" >&2
    exit 1
fi
