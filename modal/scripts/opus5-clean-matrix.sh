#!/bin/bash
exec >> /tmp/opus5-clean-matrix.log 2>&1
echo "=== $(date -Is) launching clean 6-cell matrix on non-preemptible capacity"
set -a; source ~/.config/jcode/anthropic.env; set +a
export JCODE_BENCH_JCODE_BIN=/home/jeremy/.jcode/scratch/opus5-build/target/release/jcode
export JCODE_BENCH_JCODE_VERSION="$($JCODE_BENCH_JCODE_BIN --version)"
export JCODE_BENCH_JCODE_SHA256="$(sha256sum $JCODE_BENCH_JCODE_BIN | cut -d' ' -f1)"
cd /home/jeremy/jcode-bench
~/.local/share/uv/tools/modal/bin/python modal/opus5_launch.py --mode full
echo "EXIT=$? $(date -Is)"
