#!/bin/bash
# measure-two-takes.sh — two consecutive real takes (camera PiP) against a
# packaged FocuSee Clone build, with per-window CPU sampling. Evidence harness
# for the "resources not released after a take → second take lags" fix.
#
# Windows cut from the app log step lines (unix epoch stamped as they appear):
#   take1   = [take1:control-pill-live .. take1:stop-signalled]
#   between = [take1:stop-signalled .. take2:control-pill-live]
#   take2   = [take2:control-pill-live .. take2:stop-signalled]
#   idle    = [ALL_OK+5 .. ALL_OK+45]  ← recording is over here: CPU should
#             drop to ~0 (pre-fix it keeps the bake loop + camera alive)
#
# usage: measure-two-takes.sh <label> <app-bundle-path> [rec_ms]
set -u
LABEL="$1"; APP="$2"; REC_MS="${3:-8000}"
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/runs/$LABEL"; mkdir -p "$OUT"
UD=/tmp/focusee-twotake-ud
rm -rf "$UD"; mkdir -p "$UD"
LOG="$OUT/app.log"; : > "$LOG"

echo "[2t] label=$LABEL app=$APP rec_ms=$REC_MS"
open --stdout "$LOG" --stderr "$OUT/app.err" "$APP" --args \
  --e2e-rec --e2e-rec-takes=2 --e2e-rec-cam --e2e-rec-ms="$REC_MS" \
  --e2e-rec-hold --focusee-user-data "$UD"

# --- locate this instance's main pid (private userData marker in argv) ---
MAINPID=""
for i in $(seq 1 60); do
  sleep 1
  MAINPID="$(pgrep -f "focusee-user-data $UD" | head -1)"
  [ -n "$MAINPID" ] && break
done
[ -z "$MAINPID" ] && { echo "[2t] FAIL: app never started"; exit 1; }
echo "[2t] main pid=$MAINPID (+${i}s)"

# --- window timestamps straight off the app log ---
( tail -n +1 -f "$LOG" | while IFS= read -r line; do
    case "$line" in
      *":control-pill-live"*|*":stop-signalled"*|*"ALL_OK"*|*":project-saved"*|*":camera-preview-window-live"*)
        printf '%s %s\n' "$(date +%s)" "$line" >> "$OUT/windows.txt" ;;
    esac
  done ) &
TAIL_JOB=$!

# --- continuous CPU sampling for the whole session (killed at the end) ---
date +%s > "$OUT/top-start.txt"
top -l 2000 -s 2 -o cpu -stats pid,cpu,command > "$OUT/top.txt" 2>&1 &
TOP_JOB=$!

# --- wait for the takes to finish (ALL_OK), then hold for the idle window ---
DONE=0
for i in $(seq 1 600); do
  sleep 1
  grep -q "ALL_OK" "$LOG" && { DONE=1; break; }
  kill -0 "$MAINPID" 2>/dev/null || break
done
if [ "$DONE" != 1 ]; then
  echo "[2t] WARN: no ALL_OK within 600s (check $LOG)"
fi
echo "[2t] takes finished; sampling 50s idle-after window"
sleep 50

# --- capture this instance's helper classification + camera state ---
{
  echo "MAIN $MAINPID"
  for p in $(pgrep -P "$MAINPID"); do
    args=$(ps -p "$p" -o args= 2>/dev/null) || continue
    case "$args" in
      *type=gpu-process*) echo "GPU $p";;
      *utility-sub-type=video_capture*) echo "VCAM $p";;
      *type=renderer*) echo "RENDERER $p";;
    esac
  done
} > "$OUT/pids.txt"
pgrep -fl VDCAssistant > "$OUT/vdcassistant.txt" 2>&1 || echo "no VDCAssistant process" > "$OUT/vdcassistant.txt"
log show --last 4m --predicate 'process == "VDCAssistant"' --style compact 2>/dev/null | tail -40 > "$OUT/vdcassistant-log.txt" || true

# --- stop samplers, then stop OUR instance only (private ud marker) ---
kill "$TOP_JOB" 2>/dev/null; kill "$TAIL_JOB" 2>/dev/null
date +%s > "$OUT/top-end.txt"
pkill -f "focusee-user-data $UD" 2>/dev/null
sleep 2
pkill -9 -f "user-data-dir=$UD" 2>/dev/null

# --- artifacts: e2e report + codec probe of both takes ---
cp "$UD/focusee-clone/artifacts/e2e-rec-report.json" "$OUT/rec-report.json" 2>/dev/null || true
n=0
for d in "$UD"/focusee-clone/projects/rec-*; do
  [ -f "$d/recording.webm" ] || continue
  n=$((n+1))
  ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,profile,width,height \
    -show_entries format=duration,size -of json "$d/recording.webm" > "$OUT/probe-take$n.json" 2>/dev/null
done
python3 "$HERE/summarize-two-takes.py" "$OUT" || true
echo "[2t] done $LABEL"
