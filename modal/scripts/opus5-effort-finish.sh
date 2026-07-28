#!/bin/bash
# Wait for every cell of an effort sweep to reach a terminal state, then run the
# validity gate and write the reports. Idempotent and safe to re-run.
#
# Unlike opus5-finish.sh this takes the manifest as an argument and stops at the
# reports: the website payload builder encodes a two-cell head-to-head claim, so
# a three-effort sweep must not be pushed through it without a gate that
# understands the extra axis.
exec >> /tmp/opus5-effort-finish.log 2>&1
cd /home/jeremy/jcode-bench || exit 1

MANIFEST=${1:-modal/launches/20260728T084428Z-opus5-full.json}
STEM=${2:-2026-07-28-opus5-effort-sweep}
PY=~/.local/share/uv/tools/modal/bin/python

set -a
source ~/.config/jcode/anthropic.env
set +a

echo "=== $(date -Is) effort-sweep watcher pid=$$ manifest=$MANIFEST"
for i in $(seq 1 600); do
  OUT=$($PY modal/validate_opus5_run.py "$MANIFEST" 2>&1)
  CODE=$?
  if [ "$CODE" != 2 ]; then
    echo "=== $(date -Is) all cells terminal (validator exit=$CODE)"
    echo "$OUT"

    $PY modal/validate_opus5_run.py "$MANIFEST" \
      --json-output "modal/runs/$STEM-validation.json" >/dev/null 2>&1
    $PY modal/collect_results.py "$MANIFEST" \
      --json-output "modal/runs/$STEM-results.json" \
      --markdown-output "modal/runs/$STEM-results.md" \
      --allow-incomplete
    echo "REPORTS_WRITTEN $(date -Is)"
    exit 0
  fi
  echo "$(date -Is) pending=$(echo "$OUT" | grep -c '^PENDING') ok=$(echo "$OUT" | grep -c '^OK') invalid=$(echo "$OUT" | grep -c '^INVALID')"
  sleep 300
done
echo "TIMED_OUT $(date -Is)"
