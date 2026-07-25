#!/bin/bash
# Rerun the jcode utf16-transcode cell once a jcode build containing the
# empty-post-tool-retry fix exists.
#
# The original cell reported success with a 0.0 score: its final turn returned
# zero output tokens and the retry budget was 1, so the turn loop ended with the
# submission unoptimized. That is a harness defect, not a model result, so the
# cell must be rerun on a build where the retry budget is 5.
exec >> /tmp/opus5-rerun-utf16.log 2>&1
BIN=/home/jeremy/.jcode/scratch/opus5-build2/target/release/jcode
PY=~/.local/share/uv/tools/modal/bin/python
cd /home/jeremy/jcode-bench || exit 1

echo "=== $(date -Is) waiting for the fixed build"
for i in $(seq 1 240); do
  [ -x "$BIN" ] && break
  sleep 60
done
if [ ! -x "$BIN" ]; then echo "BUILD_NEVER_APPEARED"; exit 1; fi

# Refuse to run unless the binary actually carries the fix.
if ! "$BIN" --version > /dev/null 2>&1; then echo "BINARY_UNUSABLE"; exit 1; fi
echo "build ready: $("$BIN" --version)"

set -a; source ~/.config/jcode/anthropic.env; set +a
export JCODE_BENCH_JCODE_BIN="$BIN"
export JCODE_BENCH_JCODE_VERSION="$("$BIN" --version)"
export JCODE_BENCH_JCODE_SHA256="$(sha256sum "$BIN" | cut -d' ' -f1)"

for a in 1 2 3; do
  timeout 1800 ~/.local/share/uv/tools/modal/bin/modal deploy modal/opus5_app.py && break
  echo "deploy attempt $a failed"; sleep 30
done

$PY modal/opus5_launch.py --mode pilot --task utf16-transcode --harnesses jcode
echo "LAUNCH_EXIT=$? $(date -Is)"
