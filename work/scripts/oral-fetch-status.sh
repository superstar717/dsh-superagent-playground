#!/usr/bin/env bash
# 从 PC 拉取所有 job 状态到 Mac 本地缓存，供 job-status.py 读取。
#
# 背景（2026-11-21 实测）：SMB 挂载经 Tailscale 会话建立成功但目录 IO 死锁、
# 局域网直连 445 被拒；SSH（administrator 公钥）全程秒回且 sftp 往返 1.3s。
# 因此状态同步走 SSH 拉取：PC 上 D:\oral 是唯一副本，Mac 只拉 status/handoff 缓存。
#
# 用法：
#   oral-fetch-status.sh              # 拉一次
#   watch 15 oral-fetch-status.sh     # 外部循环；或 oral-fetch-status.sh --watch 15
#
# 环境变量：
#   ORAL_SSH   默认 administrator@pc-20230915xmxx（Tailscale 名，也可用 IP）
#   ORAL_CACHE 默认 ~/oral-cache
#
# 退出码：0 拉取成功；2 SSH 连不上；3 PC 上 jobs 目录为空或不存在（缓存清空）。
set -uo pipefail

WATCH=0
[[ "${1:-}" == "--watch" ]] && { WATCH="${2:-15}"; shift 2; }

HOST="${ORAL_SSH:-administrator@pc-20230915xmxx}"
CACHE="${ORAL_CACHE:-$HOME/oral-cache}"

fetch_once() {
  local tmp
  tmp=$(mktemp -d) || return 1
  mkdir -p "$CACHE/jobs"

  # 注意：SSH→powershell -Command - 的 stdin 通道会把跨行脚本打碎静默不执行
  #（2026-11-21 实测），因此必须用 -EncodedCommand（UTF-16LE base64）。
  PS_SCRIPT='
$ProgressPreference = "SilentlyContinue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$files = Get-ChildItem "D:\oral\jobs\*\90-meta\status.json" -ErrorAction SilentlyContinue
if (-not $files) { exit 3 }
foreach ($f in $files) {
  "===JOB=== " + $f.Directory.Parent.Name
  Get-Content $f.FullName -Raw
  "===END==="
}
'
  B64=$(python3 -c "import base64,sys; print(base64.b64encode(sys.stdin.buffer.read().decode('utf-8').encode('utf-16-le')).decode())" <<PSEOF
$PS_SCRIPT
PSEOF
)
  # 注意：不要写 `if ! ssh ...; then rc=$?` —— `!` 会把 $? 覆盖为 0（bash 经典坑）
  ssh -o BatchMode=yes -o ConnectTimeout=8 "$HOST" "powershell -NoProfile -EncodedCommand $B64" >"$tmp/raw.txt" 2>"$tmp/ssh.err"
  local rc=$?
  if [[ $rc -ne 0 ]]
  then
    rm -rf "$tmp"
    if [[ $rc -eq 3 ]]; then
      find "$CACHE/jobs" -mindepth 1 -maxdepth 1 -type d -exec rm -rf {} + 2>/dev/null
      return 0
    fi
    return 2
  fi

  # 逐 job 原子覆盖缓存
  local job="" acc=()
  flush() {
    if [[ -n "$job" ]]; then
      mkdir -p "$CACHE/jobs/$job/90-meta"
      printf '%s\n' "${acc[@]}" > "$CACHE/jobs/$job/90-meta/status.json.new"
      mv -f "$CACHE/jobs/$job/90-meta/status.json.new" "$CACHE/jobs/$job/90-meta/status.json"
      touch "$CACHE/jobs/$job/90-meta/.fetched"
    fi
  }
  local line
  while IFS= read -r line; do
    line="${line%$'\r'}"   # PowerShell 输出 CRLF，剥掉 CR 否则 job 名会带上隐藏字符
    if [[ "$line" == "===JOB==="* ]]; then flush; job="${line#===JOB=== }"; acc=()
    elif [[ "$line" == "===END===" ]]; then flush; job=""; acc=()
    elif [[ -n "$job" ]]; then acc+=("$line")
    fi
  done < "$tmp/raw.txt"
  flush

  # 缓存里已消失的 job 清掉（PC 侧删除/归档后不再出现）
  local d name
  for d in "$CACHE/jobs"/*; do
    [[ -d "$d" ]] || continue
    name=$(basename "$d")
    grep -qF "===JOB=== $name" "$tmp/raw.txt" || rm -rf "$d"   # 不加 $ 锚：raw 行尾带 CR
  done
  rm -rf "$tmp"
  return 0
}

rc=0
fetch_once || rc=$?
[[ $rc -ne 0 ]] && { echo "fetch failed (rc=$rc)：PC 不可达？" 1>&2; exit $rc; }

if [[ $WATCH -gt 0 ]]; then
  while true; do
    sleep "$WATCH"
    fetch_once || echo "fetch failed once, retrying" 1>&2
  done
fi
exit 0
