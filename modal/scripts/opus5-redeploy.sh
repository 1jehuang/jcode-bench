#!/bin/bash
exec >> /tmp/opus5-redeploy.log 2>&1
echo "=== $(date -Is) redeploy with checkpoint-resume"
set -a; source ~/.config/jcode/anthropic.env; set +a
export JCODE_BENCH_JCODE_BIN=/home/jeremy/.jcode/scratch/opus5-build/target/release/jcode
export JCODE_BENCH_JCODE_VERSION="$($JCODE_BENCH_JCODE_BIN --version)"
export JCODE_BENCH_JCODE_SHA256="$(sha256sum $JCODE_BENCH_JCODE_BIN | cut -d' ' -f1)"
cd /home/jeremy/jcode-bench
for a in 1 2 3 4 5; do
  timeout 1800 ~/.local/share/uv/tools/modal/bin/modal deploy modal/opus5_app.py && { echo "DEPLOY_OK attempt=$a"; exit 0; }
  echo "attempt $a failed"; sleep 30
done
echo DEPLOY_GAVE_UP
