#!/bin/bash
# kb-responder 重载门禁：语法检查 → 路由回归自测 → 重启 launchd。
# 自测不过就不重启（2026-11-13 机制化，工单 c568a58a9d7e）。
# 用法：bash ~/姜胡说/scripts/kb-responder-reload.sh
# 说明：改动 kb-responder.py 后必须走这个脚本重启；直接 kickstart 会跳过回归门禁。
set -euo pipefail

LIVE_DIR="${HOME}/姜胡说/scripts"
LABEL="com.user.kb.responder"

echo "[1/3] 语法检查"
python3 -m py_compile "${LIVE_DIR}/kb-responder.py"

echo "[2/3] 路由回归自测（不过则中止，不重启）"
python3 "${LIVE_DIR}/kb-responder-selftest.py"

echo "[3/3] 重启 launchd 任务 ${LABEL}"
launchctl kickstart -k "gui/$(id -u)/${LABEL}"
sleep 2
tail -n 5 "${HOME}/姜胡说/logs/kb-responder.log"
echo "重载完成。"
