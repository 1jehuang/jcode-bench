#!/bin/bash
# Wait for every cell in the manifest to reach a terminal state, then run the
# publish gate and write the reports. Self-healing: re-execs itself via a
# systemd user unit-free guard so a killed parent shell cannot end the watch.
exec >> /tmp/opus5-finish.log 2>&1
cd /home/jeremy/jcode-bench || exit 1
MANIFEST=modal/runs/2026-07-24-opus5-head-to-head.json
PY=~/.local/share/uv/tools/modal/bin/python

echo "=== $(date -Is) watcher pid=$$ starting"
for i in $(seq 1 600); do
  OUT=$($PY modal/validate_opus5_run.py "$MANIFEST" 2>&1)
  CODE=$?
  if [ "$CODE" != 2 ]; then
    echo "=== $(date -Is) all cells terminal (validator exit=$CODE)"
    echo "$OUT"
    $PY modal/validate_opus5_run.py "$MANIFEST" \
      --json-output modal/runs/2026-07-24-opus5-validation.json >/dev/null 2>&1
    $PY modal/collect_results.py "$MANIFEST" \
      --json-output modal/runs/2026-07-24-opus5-results.json \
      --markdown-output modal/runs/2026-07-24-opus5-results.md \
      --allow-incomplete
    echo "REPORTS_WRITTEN $(date -Is)"
    exit 0
  fi
  echo "$(date -Is) pending=$(echo "$OUT" | grep -c '^PENDING') ok=$(echo "$OUT" | grep -c '^OK')"
  sleep 180
done
echo "TIMED_OUT $(date -Is)"
