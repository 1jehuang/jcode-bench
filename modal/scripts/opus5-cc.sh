#!/bin/bash
exec >> /tmp/opus5-cc.log 2>&1
echo "=== $(date -Is) launching remaining claude-code cells"
set -a; source ~/.config/jcode/anthropic.env; set +a
export JCODE_BENCH_JCODE_BIN=/home/jeremy/.jcode/scratch/opus5-build/target/release/jcode
export JCODE_BENCH_JCODE_VERSION="$($JCODE_BENCH_JCODE_BIN --version)"
export JCODE_BENCH_JCODE_SHA256="$(sha256sum $JCODE_BENCH_JCODE_BIN | cut -d' ' -f1)"
cd /home/jeremy/jcode-bench
~/.local/share/uv/tools/modal/bin/python modal/opus5_launch.py --mode full \
  --tasks float-print utf16-transcode --harnesses claude-code
echo "LAUNCH_EXIT=$? $(date -Is)"
