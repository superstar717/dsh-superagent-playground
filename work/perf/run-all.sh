#!/bin/bash
# Interleaved A/B measurement: nocam then cam blocks, codec alternated.
set -u
cd ~/src/verify-hw-encode-8dae0e8b1c01
M=work/perf/measure-take.sh
bash $M r2-vp9-nocam  vp9 0 14000
sleep 6
bash $M r3-vp9-nocam  vp9 0 14000
sleep 6
bash $M r4-h264-nocam h264 0 14000
sleep 6
bash $M r5-h264-cam   h264 1 14000
sleep 6
bash $M r6-vp9-cam    vp9 1 14000
sleep 6
bash $M r7-vp9-cam    vp9 1 14000
sleep 6
bash $M r8-h264-cam   h264 1 14000
echo ALL_RUNS_DONE
