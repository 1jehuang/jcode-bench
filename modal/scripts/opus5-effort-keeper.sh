#!/bin/bash
# Supervise the effort-sweep watcher and progress logger for the run's duration.
#
# PID files rather than pgrep: matching on a command-line substring also matched
# the keeper's own argv, which raced and spawned duplicate watchers. A PID file
# plus a liveness check on that exact PID is unambiguous.
exec >> /tmp/opus5-effort-keeper.log 2>&1
SCRIPTS=/home/jeremy/jcode-bench/modal/scripts
RUN=/tmp/opus5-effort-run-state
mkdir -p "$RUN"

alive() {  # alive <pidfile>
  local f=$1 pid
  [ -f "$f" ] || return 1
  pid=$(cat "$f" 2>/dev/null) || return 1
  [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

start() {  # start <name> <script>
  local name=$1 script=$2
  setsid bash "$script" &
  echo $! > "$RUN/$name.pid"
  echo "$(date -Is) started $name pid=$!"
}

# Reap children from a previous keeper generation. Without this, a restarted
# keeper adds a second watcher instead of adopting the running one, and repeated
# restarts multiply pollers against the results volume.
reap_orphans() {  # reap_orphans <name> <pattern>
  local name=$1 pattern=$2 keep=""
  [ -f "$RUN/$name.pid" ] && keep=$(cat "$RUN/$name.pid" 2>/dev/null)
  for pid in $(pgrep -f "$pattern"); do
    [ "$pid" = "$keep" ] && continue
    [ "$pid" = "$$" ] && continue
    kill "$pid" 2>/dev/null && echo "$(date -Is) reaped orphan $name pid=$pid"
  done
}

reap_orphans finish "bash .*opus5-effort-finish\.sh"
reap_orphans progress "bash .*opus5-effort-progress\.sh"

echo "$(date -Is) effort keeper pid=$$ supervising"
for i in $(seq 1 900); do
  if grep -q "REPORTS_WRITTEN" /tmp/opus5-effort-finish.log 2>/dev/null; then
    echo "$(date -Is) reports written; keeper exiting"
    exit 0
  fi
  alive "$RUN/finish.pid"   || start finish   "$SCRIPTS/opus5-effort-finish.sh"
  alive "$RUN/progress.pid" || start progress "$SCRIPTS/opus5-effort-progress.sh"
  sleep 60
done
echo "$(date -Is) keeper loop exhausted"
