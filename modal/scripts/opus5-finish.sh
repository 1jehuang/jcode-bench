#!/bin/bash
# Wait for all 6 cells to reach a terminal state, then run the publish gate and
# generate the report. Detached so harness reloads cannot orphan it.
exec >> /tmp/opus5-finish.log 2>&1
cd /home/jeremy/jcode-bench
MANIFEST=modal/runs/2026-07-24-opus5-head-to-head.json
PY=~/.local/share/uv/tools/modal/bin/python

for i in $(seq 1 480); do   # up to ~24h at 3-minute intervals
  OUT=$($PY modal/validate_opus5_run.py "$MANIFEST" 2>&1)
  CODE=$?
  if [ "$CODE" != 2 ]; then
    echo "=== $(date -Is) all cells terminal (validator exit=$CODE)"
    echo "$OUT"
    $PY modal/validate_opus5_run.py "$MANIFEST" \
      --json-output modal/runs/2026-07-24-opus5-validation.json > /dev/null 2>&1
    $PY modal/collect_results.py "$MANIFEST" \
      --json-output modal/runs/2026-07-24-opus5-results.json \
      --markdown-output modal/runs/2026-07-24-opus5-results.md \
      --allow-incomplete
    echo "REPORTS_WRITTEN $(date -Is)"
    exit 0
  fi
  PENDING=$(echo "$OUT" | grep -c '^PENDING')
  echo "$(date -Is) pending=$PENDING"
  sleep 180
done
echo "TIMED_OUT waiting for cells"
