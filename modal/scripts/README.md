# Detached run scripts for the Opus 5 head-to-head

These are the exact scripts used for the 2026-07-24 Claude Opus 5 comparison.
They exist because the interactive path was unreliable in two specific ways:

1. **Harness reloads orphan long jobs.** A `modal deploy` uploading a 127 MB
   binary, or a 20-hour launch watcher, must not be a child of an agent session
   that can be replaced mid-flight. Every script is started with
   `setsid ... < /dev/null &` and writes to its own log under `/tmp`.
2. **Large-binary uploads stall.** One deploy dropped to ~1.5 KB/s and had to be
   killed manually, so `opus5-run.sh` retries the deploy up to five times with a
   30-minute timeout per attempt.

| script | purpose |
|---|---|
| `opus5-run.sh` | pin the binary, deploy with retries, then launch the jcode cells |
| `opus5-cc.sh` | launch the remaining Claude Code cells |
| `opus5-monitor.sh` | log a compact status line for all six cells every 10 minutes |
| `opus5-finish.sh` | wait for every cell to reach a terminal state, then run the publish gate and write the reports |
| `opus5-keeper.sh` | restart the finisher if it ever dies, and exit once the reports exist |
| `opus5-progress.sh` | log a compact per-cell score line every 30 minutes |
| `opus5-clean-matrix.sh` | launch all six cells simultaneously on non-preemptible capacity |
| `opus5-redeploy.sh` | redeploy the app with the pinned binary, retrying stalled uploads |

Each script hardcodes the pinned binary path used for that run
(`~/.jcode/scratch/opus5-build/target/release/jcode`, `jcode v0.56.19-dev
(b9b1470ad)`). Update the path and re-pin before reusing them.

`opus5-finish.sh` runs the whole publication pipeline once the matrix is
terminal: the validity gate, the result reports, and then the website publish
gate, which refuses on its own if the run is unpublishable or jcode did not win.

The keeper exists because `setsid` alone was not enough: killing the shell that
had spawned a watcher also took the watcher down mid-run. The keeper polls every
two minutes, relaunches `opus5-finish.sh` if it is missing, and stops once
`REPORTS_WRITTEN` appears in the finisher log.

Logs land at `/tmp/opus5-run.log`, `/tmp/opus5-cc.log`,
`/tmp/opus5-monitor.log`, and `/tmp/opus5-finish.log`.
