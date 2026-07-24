#!/bin/bash
# Deploy (with retries for flaky large-binary uploads), then launch the jcode
# cells. Fully detached so harness reloads cannot orphan it.
exec >> /tmp/opus5-run.log 2>&1
echo "=== $(date -Is) starting"
set -a; source ~/.config/jcode/anthropic.env; set +a
export JCODE_BENCH_JCODE_BIN=/home/jeremy/.jcode/scratch/opus5-build/target/release/jcode
export JCODE_BENCH_JCODE_VERSION="$($JCODE_BENCH_JCODE_BIN --version)"
export JCODE_BENCH_JCODE_SHA256="$(sha256sum $JCODE_BENCH_JCODE_BIN | cut -d' ' -f1)"
cd /home/jeremy/jcode-bench
echo "pinning $JCODE_BENCH_JCODE_VERSION / $JCODE_BENCH_JCODE_SHA256"

for attempt in 1 2 3 4 5; do
  echo "--- deploy attempt $attempt $(date -Is)"
  if timeout 1800 ~/.local/share/uv/tools/modal/bin/modal deploy modal/opus5_app.py; then
    echo "DEPLOY_OK attempt=$attempt"
    break
  fi
  echo "deploy attempt $attempt failed; retrying"
  sleep 30
  if [ "$attempt" = 5 ]; then echo "DEPLOY_GAVE_UP"; exit 1; fi
done

echo "--- launching jcode cells $(date -Is)"
~/.local/share/uv/tools/modal/bin/python modal/opus5_launch.py --mode full \
  --tasks json-unescape float-print utf16-transcode --harnesses jcode
echo "LAUNCH_EXIT=$? $(date -Is)"
