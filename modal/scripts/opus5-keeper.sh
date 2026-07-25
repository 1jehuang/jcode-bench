#!/bin/bash
exec >> /tmp/opus5-keeper.log 2>&1
SCRIPTS=/home/jeremy/jcode-bench/modal/scripts

for i in $(seq 1 400); do
  # The progress logger is supervised too: it kept dying with the shell that
  # spawned it, leaving the run unobserved.
  if ! pgrep -f "bash .*opus5-progress\.sh" > /dev/null; then
    if ! grep -q "REPORTS_WRITTEN" /tmp/opus5-finish.log 2>/dev/null; then
      echo "$(date -Is) progress logger down, restarting"
      setsid bash "$SCRIPTS/opus5-progress.sh" < /dev/null &
      sleep 5
    fi
  fi
  if ! pgrep -f "bash .*opus5-finish\.sh" > /dev/null; then
    if grep -q "REPORTS_WRITTEN" /tmp/opus5-finish.log 2>/dev/null; then
      echo "$(date -Is) reports written, keeper exiting"; exit 0
    fi
    echo "$(date -Is) watcher down, restarting"
    setsid bash /home/jeremy/jcode-bench/modal/scripts/opus5-finish.sh < /dev/null &
  fi
  sleep 120
done
