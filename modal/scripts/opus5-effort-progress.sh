#!/bin/bash
# Log a compact progress line for every cell of an effort sweep, every 30
# minutes, so a multi-hour 18-cell run can be reviewed without interactive
# polling.
exec >> /tmp/opus5-effort-progress.log 2>&1
MV=~/.local/share/uv/tools/modal/bin/modal
PY=~/.local/share/uv/tools/modal/bin/python
SCRIPTS=/home/jeremy/jcode-bench/modal/scripts
MANIFEST=${1:-/home/jeremy/jcode-bench/modal/launches/20260728T084428Z-opus5-full.json}
cd /home/jeremy/jcode-bench || exit 1

set -a
source ~/.config/jcode/anthropic.env
set +a

for i in $(seq 1 60); do
  echo "=== $(date -Is)"
  for r in $($PY -c "
import json,sys
print(' '.join(x['run_id'] for x in json.load(open(sys.argv[1]))['runs']))" "$MANIFEST"); do
    # Read scores from the agent log, not from a checkpoint: checkpoints only
    # snapshot when the submission tree changes, so a cell that graded several
    # times without editing files keeps reporting a stale baseline score.
    LOG=$($MV volume get jcode-bench-v1-results "runs/$r/agent.log" - 2>/dev/null)
    S=$(printf '%s' "$LOG" | $PY "$SCRIPTS/opus5_scores.py" 2>/dev/null)
    # Log size distinguishes a genuinely stalled cell from one mid-generation:
    # Opus 5 can spend 6+ minutes on one 65k-token turn, during which the score
    # curve looks frozen, so score alone is not a liveness signal.
    BYTES=$(printf '%s' "$LOG" | wc -c)
    echo "  $(echo "$r" | sed 's/.*opus5-//'): $S log=${BYTES}B"
  done
  sleep 1800
done
