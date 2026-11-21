#!/bin/bash
# Monitor the Q2_0 download on the PC until it completes, fails visibly, or stalls.
# Prints a status block per cycle; exits on COMPLETE / FAILURE / STALLED so the caller wakes up.
S1=37623740192
S2=28800138432
PC=Administrator@100.80.147.68
LOG=/tmp/q2_0_monitor.log
: > "$LOG"
last_total=-1
stalls=0
for i in $(seq 1 80); do
  out=$(ssh -o ConnectTimeout=10 -o BatchMode=yes -o ServerAliveInterval=5 -o ServerAliveCountMax=3 \
        "$PC" "powershell -NoProfile -ExecutionPolicy Bypass -File C:\\Users\\Administrator\\q2_status.ps1" 2>&1)
  {
    echo "===== $(date '+%H:%M:%S') cycle $i ====="
    echo "$out"
  } >> "$LOG"

  f1=$(echo "$out" | awk -F'[ =]' '/00001-of-00002.gguf final=/{print $3+0; exit}')
  p1=$(echo "$out" | awk -F'[ =]' '/00001-of-00002.gguf final=/{print $5+0; exit}')
  f2=$(echo "$out" | awk -F'[ =]' '/00002-of-00002.gguf final=/{print $3+0; exit}')
  p2=$(echo "$out" | awk -F'[ =]' '/00002-of-00002.gguf final=/{print $5+0; exit}')
  total=$(( ${f1:-0} + ${p1:-0} + ${f2:-0} + ${p2:-0} ))

  if echo "$out" | grep -q "\[done\] both shards"; then
    echo "COMPLETE: [done] marker in log" >> "$LOG"; break; fi
  if [ "${f1:-0}" -eq "$S1" ] && [ "${f2:-0}" -eq "$S2" ]; then
    echo "COMPLETE: both shards at full size" >> "$LOG"; break; fi
  if echo "$out" | grep -qE "\[fail\]|EXITCODE=[1-9]"; then
    echo "FAILURE: error line in log" >> "$LOG"; break; fi

  if [ "$total" -le "$last_total" ]; then
    stalls=$((stalls + 1))
    echo "STALL$stalls: no growth since last cycle (total=$total)" >> "$LOG"
    if [ "$stalls" -ge 3 ]; then echo "STALLED: no growth for 3 cycles" >> "$LOG"; break; fi
  else
    stalls=0
  fi
  last_total=$total
  sleep 240
done
echo "monitor loop ended" >> "$LOG"
tail -30 "$LOG"
