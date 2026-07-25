#!/bin/bash
# Log a compact progress line for all six cells every 30 minutes, so the run can
# be reviewed without frequent interactive polling.
exec >> /tmp/opus5-progress.log 2>&1
MV=~/.local/share/uv/tools/modal/bin/modal
PY=~/.local/share/uv/tools/modal/bin/python
cd /home/jeremy/jcode-bench
for i in $(seq 1 60); do
  echo "=== $(date -Is)"
  for r in $($PY -c "
import json;print(' '.join(x['run_id'] for x in json.load(open('modal/runs/2026-07-24-opus5-head-to-head.json'))['runs']))"); do
    CK=$($MV volume ls jcode-bench-v1-results runs/$r/checkpoints 2>/dev/null | sed 's|.*checkpoints/||' | sort | tail -1)
    S=$($MV volume get jcode-bench-v1-results runs/$r/checkpoints/$CK/scores.jsonl - 2>/dev/null | $PY -c "
import sys,json
v=[json.loads(l)['score'] for l in sys.stdin if l.strip() and l.startswith('{')]
print(f'{len(v)} grades best={max(v):+.4f}' if v else 'no grades')" 2>/dev/null)
    # Log size distinguishes a genuinely stalled cell from one mid-generation.
    # Opus 5 can spend 6+ minutes on a single 65k-token turn, during which the
    # score curve and even the streamed log look frozen, so score alone is not a
    # liveness signal.
    BYTES=$($MV volume get jcode-bench-v1-results runs/$r/agent.log - 2>/dev/null | wc -c)
    echo "  $(echo $r | sed 's/.*opus5-//'): $S log=${BYTES}B"
  done
  sleep 1800
done
