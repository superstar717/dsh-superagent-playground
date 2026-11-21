#!/usr/bin/env bash
# 12G 显存 PC「口播视频」能力体检（macOS / Linux / WSL2 通用）
#
# 用法：
#   bash pc-video-capability-check.sh              # 人类可读报告
#   bash pc-video-capability-check.sh --json       # 机器可读（便于回传）
#   bash pc-video-capability-check.sh --vram-gb 12 # 模拟 12G 档（没插卡也能预览分档表）
#
# 只读探测，不安装任何东西。判据来自 work/12G显存PC做口播视频-可行性与分工-2026-11-21.md，
# 显存阈值是「官方/社区公开口径」，不是本脚本实测；脚本只负责把本机事实采集出来做对照。

set -uo pipefail

JSON=0
FAKE_VRAM_GB=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --json) JSON=1 ;;
    --vram-gb) FAKE_VRAM_GB="${2:-}"; shift ;;
    *) echo "未知参数: $1" >&2; exit 2 ;;
  esac
  shift
done

have() { command -v "$1" >/dev/null 2>&1; }
num()  { awk -v v="${1:-0}" 'BEGIN{printf "%.0f", v}'; }

# ---------- 1. GPU ----------
GPU_NAME=""; VRAM_MB=0; DRIVER=""; CUDA_VER=""; GPU_OK=0
if have nvidia-smi && nvidia-smi >/dev/null 2>&1; then
  GPU_OK=1
  GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 | sed 's/^ *//;s/ *$//')
  VRAM_MB=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -dc '0-9')
  DRIVER=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -1 | sed 's/^ *//;s/ *$//')
  CUDA_VER=$(nvidia-smi 2>/dev/null | sed -n 's/.*CUDA Version: *\([0-9.]*\).*/\1/p' | head -1)
fi
VRAM_MB=${VRAM_MB:-0}
VRAM_GB=$(( (VRAM_MB + 512) / 1024 ))
if [[ -n "$FAKE_VRAM_GB" ]]; then   # 模拟档位，用于在没插卡的机器上预览分档表
  GPU_OK=1; VRAM_GB="$FAKE_VRAM_GB"; GPU_NAME="(模拟 ${FAKE_VRAM_GB}G 显存)"; VRAM_MB=$(( FAKE_VRAM_GB * 1024 ))
fi

# ---------- 2. 内存 / 磁盘 ----------
RAM_GB=0
if [[ "$(uname -s)" == "Darwin" ]]; then
  RAM_GB=$(( $(sysctl -n hw.memsize 2>/dev/null || echo 0) / 1024 / 1024 / 1024 ))
else
  if have free; then RAM_GB=$(( $(free -g 2>/dev/null | awk '/^Mem:/{print $2}') )); fi
  [[ "$RAM_GB" == "0" ]] && RAM_GB=$(( $(awk '/MemTotal/{printf "%.0f", $2/1024/1024}' /proc/meminfo 2>/dev/null || echo 0) ))
fi
DISK_FREE_GB=$(df -Pk "${HOME:-/}" 2>/dev/null | awk 'NR==2{printf "%.0f", $4/1024/1024}')

# ---------- 3. 工具链 ----------
NODE_VER=$([[ -n "$(have node && node -v 2>/dev/null)" ]] && node -v 2>/dev/null | sed 's/^v//' || echo "")
PY_VER=$( (have python3 && python3 -V 2>/dev/null) || (have python && python -V 2>/dev/null) || echo "" | sed 's/^Python //')
PY_VER=$(echo "$PY_VER" | sed 's/^Python //')
UV_VER=$(have uv && uv --version 2>/dev/null | awk '{print $2}' || echo "")
FFMPEG_VER=$(have ffmpeg && ffmpeg -version 2>/dev/null | head -1 | awk '{print $3}' || echo "")
NVENC="none"
if have ffmpeg; then
  NVENC=$(ffmpeg -hide_banner -encoders 2>/dev/null | grep -Eo 'h264_nvenc|hevc_nvenc|av1_nvenc' | sort -u | paste -sd ',' -)
  [[ -z "$NVENC" ]] && NVENC="none"
fi
IS_WSL=0
grep -qi microsoft /proc/version 2>/dev/null && IS_WSL=1

# ---------- 4. 按显存分档判定 ----------
# A=够用，B=降配可用，C=只够草稿，D=不够（走云端/模板）
verdict() {
  local need=$1 tier=$2 label=$3
  if [[ $VRAM_GB -ge $need ]]; then printf 'A\t%s\n' "$label"; else printf '%s\t%s\n' "$tier" "$label"; fi
}
rows=()
if [[ $GPU_OK -eq 0 ]]; then
  rows+=($'—\t剪辑/字幕/模板渲染（CPU 路径）：本机无 NVIDIA GPU，AI 加速环节不可用')
else
  rows+=("$(verdict 6 A '剪辑 1080p（剪映/达芬奇，NVENC 编码）')")
  rows+=("$(verdict 6 A 'TTS 声音克隆（CosyVoice2 fp16 6–8G / GPT-SoVITS 6G+）')")
  rows+=("$(verdict 4 A 'ASR 字幕（faster-whisper turbo ~2G；SenseVoice CPU 已够快）')")
  rows+=("$(verdict 6 A '唇形/人像驱动（MuseTalk 6G+ / LivePortrait 6G）')")
  rows+=("$(verdict 8 A 'LatentSync 1.5 256×256 唇形（官方 8G；1.6 512 需 18G → 12G 不够）')")
  rows+=("$(verdict 10 A 'Real-ESRGAN 1080p 2x + RIFE 补帧（叠加实测约 10.8G）')")
  rows+=("$(verdict 8 A '达芬奇 1080p 剪辑/调色（免费版单卡）')")
  rows+=("$(verdict 16 B '达芬奇 4K 时间线（12G 起步，建议代理/优化媒体）')")
  rows+=("$(verdict 14 C 'HunyuanVideo 1.5 720p 本地出片（官方 14G 起，12G 需量化/offload）')")
  rows+=("$(verdict 24 C 'Wan2.2 TI2V-5B 本地出片（官方 24G 起；12G 仅 GGUF 量化草稿）')")
  rows+=("$(verdict 80 D 'Wan2.2 A14B 官方路径（80G 起）→ 走云端')")
fi

if [[ $JSON -eq 1 ]]; then
  printf '{"gpu_ok":%d,"gpu_name":"%s","vram_mb":%d,"vram_gb":%d,"driver":"%s","cuda":"%s","ram_gb":%d,"disk_free_gb":%d,"node":"%s","python":"%s","uv":"%s","ffmpeg":"%s","nvenc":"%s","wsl":%d}\n' \
    "$GPU_OK" "$GPU_NAME" "$VRAM_MB" "$VRAM_GB" "$DRIVER" "$CUDA_VER" "$RAM_GB" "$DISK_FREE_GB" "$NODE_VER" "$PY_VER" "$UV_VER" "$FFMPEG_VER" "$NVENC" "$IS_WSL"
  exit 0
fi

echo "== 12G 显存 PC 口播视频能力体检 =="
echo "GPU        : ${GPU_NAME:-未检测到 NVIDIA GPU}"
echo "显存       : ${VRAM_GB} GB (${VRAM_MB} MB)"
echo "驱动/CUDA  : ${DRIVER:-n/a} / ${CUDA_VER:-n/a}"
echo "内存       : ${RAM_GB} GB"
echo "可用磁盘   : ${DISK_FREE_GB} GB（模型盘建议 ≥100GB）"
echo "WSL2       : $([[ $IS_WSL -eq 1 ]] && echo yes || echo no)"
echo "Node/Python: ${NODE_VER:-n/a} / ${PY_VER:-n/a}（uv ${UV_VER:-n/a}）"
echo "ffmpeg     : ${FFMPEG_VER:-n/a}；NVENC: ${NVENC}"
echo
echo "== 分档（A 够用 / B 降配 / C 只够草稿 / D 不够）=="
for r in "${rows[@]}"; do
  printf '%-2s %s\n' "${r%%$'\t'*}" "${r#*$'\t'}"
done
echo
echo "说明：阈值来自公开口径（官方 README / 社区实测），非本机实测；要在目标机确认速度，"
echo "      按文档「落地清单」跑 10s 参考音的 TTS 基准和 10s 唇形基准，记录 RTF 与显存峰值。"
if [[ $GPU_OK -eq 0 ]]; then
  echo "提示：无 NVIDIA GPU 时，剪辑、字幕、模板渲染仍可在 CPU 上做，只是慢；AI 生成类环节无法本地跑。"
fi
