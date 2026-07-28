#!/bin/bash
# Deploy the Opus 5 app and launch the full reasoning-effort sweep:
# 3 efforts (low, medium, high) x 2 harnesses (jcode solo, Claude Code)
# x 3 tasks = 18 independent cells, all on `claude-opus-5`.
#
# Detached and log-only for the same reasons as opus5-run.sh: a harness reload
# must not orphan a multi-hour deploy or launch, and large-binary uploads stall
# often enough to need retries.
exec >> /tmp/opus5-effort-sweep.log 2>&1
set -u

# A dirty working tree does not identify a build, and these numbers get
# published, so the sweep pins a binary built from a clean checkout.
BIN=/home/jeremy/.jcode/scratch/gate-clean/target/release/jcode
PY=~/.local/share/uv/tools/modal/bin/python
MODAL=~/.local/share/uv/tools/modal/bin/modal

echo "=== $(date -Is) opus5 effort sweep"
if [ ! -x "$BIN" ]; then
  echo "PIN_MISSING $BIN"
  exit 1
fi

set -a
source ~/.config/jcode/anthropic.env
set +a
export JCODE_BENCH_JCODE_BIN="$BIN"
export JCODE_BENCH_JCODE_VERSION="$("$BIN" --version)"
export JCODE_BENCH_JCODE_SHA256="$(sha256sum "$BIN" | cut -d' ' -f1)"
cd /home/jeremy/jcode-bench || exit 1
echo "pinning $JCODE_BENCH_JCODE_VERSION / $JCODE_BENCH_JCODE_SHA256"

for attempt in 1 2 3 4 5; do
  echo "--- deploy attempt $attempt $(date -Is)"
  if timeout 1800 "$MODAL" deploy modal/opus5_app.py; then
    echo "DEPLOY_OK attempt=$attempt"
    break
  fi
  echo "deploy attempt $attempt failed; retrying"
  sleep 30
  if [ "$attempt" = 5 ]; then
    echo "DEPLOY_GAVE_UP"
    exit 1
  fi
done

echo "--- launching 18 cells $(date -Is)"
$PY modal/opus5_launch.py --mode full \
  --tasks json-unescape float-print utf16-transcode \
  --harnesses jcode claude-code \
  --efforts low medium high
echo "LAUNCH_EXIT=$? $(date -Is)"
