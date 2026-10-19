#!/usr/bin/env bash
# Adam baseline v2 engine runs (T-20261019-4ab5). Run from the repo root: bash variants/adam/design/v2/run_engine.sh
# Independent jobs in parallel, each under a 90 min timeout. Logs: variants/adam/design/v2/logs/.
set -u
PY=.venv/Scripts/python
E=variants/adam/design/v2/engine.py
C=variants/adam/concepts
L=variants/adam/design/v2/logs
mkdir -p "$L"
T="timeout 5400"
$T $PY $E calibrated $C/R1-P1r-0p55-3s-sts3250-knee-hiproll.yaml --heights 0.55 0.60 > "$L/cal-R1.log" 2>&1 &          # R1 at this HEAD (post-merge planner)
$T $PY $E calibrated $C/V2a-0p55-longarm.yaml --heights 0.55 0.60 > "$L/cal-V2a.log" 2>&1 &                                 # v2 without L5c
$T $PY $E calibrated $C/V2b-0p55-l5c-longarm.yaml --heights 0.55 0.60 > "$L/cal-V2b.log" 2>&1 &                             # v2 with L5c
$T $PY -m openhumanoid.concept evaluate $C/V2a-0p55-longarm.yaml --samples 64 > "$L/mc-V2a-0p55.log" 2>&1 &
$T $PY -m openhumanoid.concept evaluate $C/V2b-0p55-l5c-longarm.yaml --samples 64 > "$L/mc-V2b-0p55.log" 2>&1 &
$T $PY -m openhumanoid.concept evaluate $C/V2a-0p60-longarm.yaml --samples 64 > "$L/mc-V2a-0p60.log" 2>&1 &
$T $PY -m openhumanoid.concept evaluate $C/R1-P1r-0p55-3s-sts3250-knee-hiproll.yaml --samples 64 > "$L/mc-R1-0p55.log" 2>&1 &
$T $PY -m openhumanoid.concept.motions.pickup $C/V2a-0p55-longarm.yaml --scan 0.15 0.52 0.025 > "$L/pk-V2a-0p55.log" 2>&1 &
$T $PY -m openhumanoid.concept.motions.pickup $C/V2a-0p60-longarm.yaml --scan 0.15 0.52 0.025 > "$L/pk-V2a-0p60.log" 2>&1 &
$T $PY -m openhumanoid.concept.motions.pickup $C/R1-P1r-0p55-3s-sts3250-knee-hiproll.yaml --scan 0.15 0.52 0.025 > "$L/pk-R1-0p55.log" 2>&1 &
wait
echo ALL-DONE
