#!/bin/bash
# Final mux: JPEG frame sequence + mixed audio track -> vertical MP4.
# Uses system ffmpeg: Remotion's bundled compositor cannot load on macOS 13.
set -euo pipefail
cd "$(dirname "$0")/.."

FFMPEG=/usr/local/bin/ffmpeg
FRAMES="${1:-/tmp/frames-full}"
FPS=$(node -p "JSON.parse(require('fs').readFileSync('src/timing.json','utf8')).fps")

mkdir -p ../out
"$FFMPEG" -y -framerate "$FPS" -i "$FRAMES/element-%04d.jpeg" -i out/audio-track.m4a \
  -c:v libx264 -crf 18 -preset medium -pix_fmt yuv420p \
  -c:a copy -movflags +faststart -shortest \
  ../out/superagent-vertical.mp4

echo "[finalize] wrote ../out/superagent-vertical.mp4"
