#!/usr/bin/env bash
# pc-bootstrap.sh — Mac 侧编排：拿到 SSH 公钥后，一次把 PC 体检跑完并把报告取回
# 用法：
#   ./pc-bootstrap.sh -u <Windows用户名> [-h 100.80.147.68] [-k ~/.ssh/id_ed25519] [--apply]
# 说明：
#   - 默认只跑体检（prep.ps1，报告写 F:\AI\logs\prep-*.json 并打印）
#   - --apply 会触发一次 UAC 提权（PC 屏幕上点「是」），再跑 prep.ps1 -Apply
set -euo pipefail

HOST="100.80.147.68"
USER_NAME=""
KEY="$HOME/.ssh/id_ed25519"
APPLY=0
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--host) HOST="$2"; shift 2;;
    -u|--user) USER_NAME="$2"; shift 2;;
    -k|--key) KEY="$2"; shift 2;;
    --apply) APPLY=1; shift;;
    *) echo "unknown arg: $1" >&2; exit 2;;
  esac
done

if [[ -z "$USER_NAME" ]]; then
  echo "用法: $0 -u <Windows用户名> [-h 100.80.147.68] [-k 私钥] [--apply]" >&2
  exit 2
fi

SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new -i "$KEY")
TARGET="$USER_NAME@$HOST"

echo "== 1. 连通性 / 身份"
ssh "${SSH_OPTS[@]}" "$TARGET" 'whoami; hostname; [System.Environment]::OSVersion.VersionString' \
  || { echo "SSH 失败：检查用户名/公钥是否装好" >&2; exit 1; }

REMOTE_DIR="C:/Users/$USER_NAME/linger-prep"
echo "== 2. 上传脚本到 $REMOTE_DIR"
ssh "${SSH_OPTS[@]}" "$TARGET" "powershell -NoProfile -Command \"New-Item -ItemType Directory -Force -Path '$REMOTE_DIR' | Out-Null\""
scp -o BatchMode=yes -o StrictHostKeyChecking=accept-new -i "$KEY" \
  "$SCRIPT_DIR/prep.ps1" "$SCRIPT_DIR/bench.ps1" "$TARGET:$REMOTE_DIR/"

echo "== 3. 只读体检"
ssh "${SSH_OPTS[@]}" "$TARGET" "powershell -NoProfile -ExecutionPolicy Bypass -File '$REMOTE_DIR/prep.ps1'"

if [[ "$APPLY" == "1" ]]; then
  echo "== 4. 提权跑 -Apply（PC 上会出现 UAC，请点「是」）"
  ssh "${SSH_OPTS[@]}" "$TARGET" \
    "powershell -NoProfile -Command \"Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','$REMOTE_DIR/prep.ps1','-Apply'\""
  echo "已触发提权；完成后可再跑一次只读体检确认。"
fi

echo "== 5. 拉回 JSON 报告（F:\AI\logs 优先，其次 %TEMP%）"
mkdir -p "$SCRIPT_DIR/reports"
for src in "F:/AI/logs/prep-*.json" "C:/Users/$USER_NAME/AppData/Local/Temp/prep-*.json"; do
  scp -o BatchMode=yes -o StrictHostKeyChecking=accept-new -i "$KEY" \
    "$TARGET:$src" "$SCRIPT_DIR/reports/" 2>/dev/null || true
done
ls -la "$SCRIPT_DIR/reports" 2>/dev/null || true
echo "完成。报告目录：$SCRIPT_DIR/reports"
