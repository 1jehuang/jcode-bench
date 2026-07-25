#!/bin/bash
exec >> /tmp/opus5-keeper.log 2>&1
for i in $(seq 1 400); do
  if ! pgrep -f "opus5-finish.sh" > /dev/null; then
    if grep -q "REPORTS_WRITTEN" /tmp/opus5-finish.log 2>/dev/null; then
      echo "$(date -Is) reports written, keeper exiting"; exit 0
    fi
    echo "$(date -Is) watcher down, restarting"
    setsid bash /home/jeremy/jcode-bench/modal/scripts/opus5-finish.sh < /dev/null &
  fi
  sleep 120
done
