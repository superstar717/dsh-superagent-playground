#!/bin/bash
# measure-take.sh — one instrumented e2e recording take on the real machine.
# usage: measure-take.sh <label> <h264|vp9> <cam 0|1> [rec_ms]
# Samples per-process CPU (top) and the editor renderer's thread stacks
# (sample) while the app records, then ffprobes the produced file.
set -u
LABEL="$1"; CODEC="$2"; CAM="$3"; REC_MS="${4:-14000}"
ROOT=~/src/verify-hw-encode-8dae0e8b1c01
APP="$ROOT/focusee-clone"
OUT="$ROOT/work/perf/runs/$LABEL"
mkdir -p "$OUT"

# --- codec state: restore committed file, then swap pickMime arrays for vp9 ---
git -C "$APP" checkout -- renderer/app.js
cp "$APP/renderer/app.js" "$OUT/app.js.as-run"   # record what actually ran
if [ "$CODEC" = vp9 ]; then
  python3 - "$APP/renderer/app.js" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read()
s = s.replace("const options = ['video/webm;codecs=h264,opus', 'video/webm;codecs=vp9,opus', 'video/webm;codecs=vp8,opus', 'video/webm'];",
              "const options = ['video/webm;codecs=vp9,opus', 'video/webm;codecs=vp8,opus', 'video/webm'];")
s = s.replace("const mime = ['video/webm;codecs=h264,opus', 'video/webm;codecs=vp9,opus', 'video/webm;codecs=vp8,opus', 'video/webm']",
              "const mime = ['video/webm;codecs=vp9,opus', 'video/webm;codecs=vp8,opus', 'video/webm']")
open(p, 'w').write(s)
PY
  echo "[measure] codec state: vp9"
else
  echo "[measure] codec state: h264 (as committed)"
fi

DATA=/tmp/hwenc-measure
UD=/tmp/hwenc-measure-ud
rm -rf "$DATA" "$UD"; mkdir -p "$DATA"

CAMFLAG=""
[ "$CAM" = 1 ] && CAMFLAG="--e2e-rec-cam"

cd "$APP"
FOCUSEE_DATA_DIR="$DATA" ./node_modules/.bin/electron . --e2e-rec $CAMFLAG \
  --e2e-rec-ms="$REC_MS" --focusee-user-data "$UD" > "$OUT/app.log" 2>&1 &
APP_JOB=$!
echo "[measure] launched pid=$APP_JOB label=$LABEL codec=$CODEC cam=$CAM"

# --- wait until the recording is actually live (pill up) ---
MAINPID=""
for i in $(seq 1 60); do
  sleep 1
  MAINPID=$(pgrep -f "electron . --e2e-rec" 2>/dev/null | head -1)
  [ -n "$MAINPID" ] && grep -q "control-pill-live ok" "$OUT/app.log" 2>/dev/null && break
done
if [ -z "$MAINPID" ] || ! grep -q "control-pill-live ok" "$OUT/app.log"; then
  echo "[measure] FAIL: recording never went live"; cat "$OUT/app.log"; wait $APP_JOB; exit 1
fi
echo "[measure] recording live at +${i}s, main pid=$MAINPID"

# --- classify children: editor renderer = first spawned --type=renderer child ---
sleep 1
EDITOR_PID=$(pgrep -P "$MAINPID" | while read p; do
  ps -p "$p" -o args= 2>/dev/null | grep -q "type=renderer" && { echo "$p"; break; }
done)
GPU_PID=$(pgrep -P "$MAINPID" | while read p; do
  ps -p "$p" -o args= 2>/dev/null | grep -q "type=gpu-process" && { echo "$p"; break; }
done)
echo "[measure] editor_renderer=$EDITOR_PID gpu=$GPU_PID"

# --- concurrent samplers over the steady window ---
(sleep 2; top -l 9 -s 2 -o cpu -stats pid,cpu,command > "$OUT/top.txt" 2>&1) &
TOP_JOB=$!
if [ -n "$EDITOR_PID" ]; then
  (sleep 3; sample "$EDITOR_PID" 8 15 -file "$OUT/renderer-sample.txt" >/dev/null 2>&1) &
  SMP_JOB=$?
else
  SMP_JOB=""
fi

# let the take finish (pill live -> rec_ms + teardown margin)
TOTAL=$(( i + REC_MS/1000 + 22 ))
for t in $(seq 1 $TOTAL); do
  kill -0 $APP_JOB 2>/dev/null || break
  sleep 1
done
wait $APP_JOB; APP_EXIT=$?
wait $TOP_JOB 2>/dev/null
[ -n "$SMP_JOB" ] && wait $SMP_JOB 2>/dev/null

# --- results ---
NEWEST=$(ls -td "$DATA"/projects/rec-* 2>/dev/null | head -1)
echo "[measure] app_exit=$APP_EXIT newest=$NEWEST"
if [ -n "$NEWEST" ] && [ -f "$NEWEST/recording.webm" ]; then
  ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,profile,width,height \
    -show_entries format=duration,size -of json "$NEWEST/recording.webm" > "$OUT/probe.json" 2>"$OUT/probe.err"
  cat "$NEWEST/e2e-rec-report.json" > "$OUT/rec-report.json" 2>/dev/null
  echo "[measure] probe: $(python3 -c "import json;d=json.load(open('$OUT/probe.json'));print(d['streams'][0]['codec_name'],d['streams'][0].get('profile'),d['formats'].get('size'),d['formats'].get('duration'))" 2>/dev/null)"
else
  echo "[measure] no recording produced"
fi
# encoder identity from the sampled stacks
if [ -f "$OUT/renderer-sample.txt" ]; then
  for pat in VideoToolbox VTCompression VTBundle openh264 WelsVideoEncoder OpenH264Encoder libvpx vp9; do
    c=$(grep -c "$pat" "$OUT/renderer-sample.txt" 2>/dev/null || true)
    [ "$c" != "0" ] && echo "[measure] stack-hits $pat=$c"
  done
fi
echo "[measure] done $LABEL"
