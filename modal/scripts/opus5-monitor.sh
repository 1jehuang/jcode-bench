#!/bin/bash
# Poll the 6-cell matrix and log a compact status line every 10 minutes.
exec >> /tmp/opus5-monitor.log 2>&1
cd /home/jeremy/jcode-bench
for i in $(seq 1 300); do
  echo "=== $(date -Is)"
  for m in modal/launches/20260724T203437Z-opus5-pilot.json \
           modal/launches/20260724T220318Z-opus5-full.json \
           modal/launches/20260724T221037Z-opus5-full.json; do
    ~/.local/share/uv/tools/modal/bin/python modal/status.py "$m" 2>/dev/null
  done
  sleep 600
done
