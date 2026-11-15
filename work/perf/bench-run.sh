#!/bin/bash
# bench-run.sh — run one bench-bake config with CPU sampling.
# usage: bench-run.sh <label> <fps> <rec 0|1> [dur_s]
set -u
LABEL="$1"; FPS="$2"; REC="$3"; DUR="${4:-15}"
ROOT=~/src/verify-hw-encode-8dae0e8b1c01
OUT="$ROOT/work/perf/runs/$LABEL"
mkdir -p "$OUT"
cd "$ROOT/focusee-clone"
./node_modules/.bin/electron "$ROOT/work/perf/bench-bake.js" --fps=$FPS --rec=$REC --dur=$DUR \
  --focusee-user-data /tmp/hwenc-bench-ud > "$OUT/app.log" 2>&1 &
MAIN=""
i=0
for i in $(seq 1 30); do
  sleep 1
  MAIN=$(pgrep -f "hwenc-bench-ud" | head -1)
  [ -n "$MAIN" ] && break
done
[ -z "$MAIN" ] && { echo "BENCH_NO_PROCESS"; exit 1; }
sleep 2
# walk ALL descendants (renderers may hang off the zygote, not the main)
DESC="$(pgrep -P "$MAIN" || true)"
LEVEL="$DESC"
for _ in 1 2 3; do
  NEXT=""
  for p in $LEVEL; do NEXT="$NEXT $(pgrep -P "$p" 2>/dev/null || true)"; done
  DESC="$DESC $NEXT"; LEVEL="$NEXT"
done
EPID=$(for p in $DESC; do ps -p "$p" -o args= 2>/dev/null | grep -q "type=renderer" && { echo "$p"; break; }; done)
GPID=$(for p in $DESC; do ps -p "$p" -o args= 2>/dev/null | grep -q "type=gpu-process" && { echo "$p"; break; }; done)
echo "main=$MAIN editor=$EPID gpu=$GPID"
{ echo "P $MAIN"; for p in $DESC; do echo "P $p"; done; } > "$OUT/pids.txt"
( top -l 14 -s 2 -o cpu -stats pid,cpu,command > "$OUT/top.txt" 2>&1 ) &
TOP=$!
if [ -n "$EPID" ]; then
  ( sleep 4; /usr/bin/sample "$EPID" 8 15 -file "$OUT/renderer-sample.txt" >/dev/null 2>&1 ) &
fi
for t in $(seq 1 $((DUR + 25))); do
  pgrep -f "hwenc-bench-ud" >/dev/null 2>&1 || break
  sleep 1
done
wait $TOP 2>/dev/null
grep "BENCH_RESULT" "$OUT/app.log" || tail -3 "$OUT/app.log"
echo "done $LABEL"
