#!/usr/bin/env bash
# Challenge-3 engine follow-ups for the R1 package (T-20261019-36f9). Run from the repo root: bash variants/adam/design/run_c3.sh <logdir>
# Each line is independent; they run in parallel (about 10-25 min on a 20-core machine).
set -u
LOG="${1:-.}"
PY=.venv/Scripts/python
D=variants/adam/design/r1_calibrated.py
C=variants/adam/concepts
$PY $D $C/R1x-ckh23-knee110.yaml --heights 0.55 0.60 --pushmax --tag c3 > "$LOG/c3-ckh.log" 2>&1 &                                  # rows 1, 2, 7, 8: half-cal, shelled, low SoC
$PY $D $C/R1x-ckh23-knee110.yaml --heights 0.55 0.60 --no-bounds --step-time 0.35 --tag step035 > "$LOG/c3-step.log" 2>&1 &         # row 6
$PY $D $C/R1x-ckh23-knee110.yaml --heights 0.55 0.60 --no-bounds --pushmax --foot-frac 0.17 --extra-latency-ms 20 --tag foot017-lat20 > "$LOG/c3-foot.log" 2>&1 &   # row 12
$PY $D $C/R1x-ch23-nosq120.yaml --heights 0.55 0.60 --pushmax > "$LOG/c3-chnosq.log" 2>&1 &                                         # row 3
$PY $D $C/R1x-ckh23-nosq120.yaml --heights 0.55 0.60 --pushmax > "$LOG/c3-ckhnosq.log" 2>&1 &                                       # row 3 control
$PY $D $C/R1x-t16h.yaml --heights 0.55 0.60 --pushmax > "$LOG/c3-t16h.log" 2>&1 &                                                   # row 4
$PY $D $C/R1x-t16hk.yaml --heights 0.55 0.60 --pushmax > "$LOG/c3-t16hk.log" 2>&1 &                                                 # row 4
$PY -m openhumanoid.concept evaluate $C/R1-P1-0p60-3s-sts3250-knee-hiproll.yaml --samples 64 > "$LOG/c3-mc-p1.log" 2>&1 &           # row 2: 64-sample MC
$PY -m openhumanoid.concept evaluate $C/R1-P1r-0p55-3s-sts3250-knee-hiproll.yaml --samples 64 > "$LOG/c3-mc-p1r.log" 2>&1 &
wait
echo ALL-DONE
