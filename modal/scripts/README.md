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
| `opus5-effort-sweep.sh` | deploy and launch the 18-cell low/medium/high effort sweep |
| `opus5-effort-finish.sh` | wait for a sweep to go terminal, then gate and write its reports |
| `opus5-effort-progress.sh` | log a per-cell score line for a sweep every 30 minutes |
| `opus5-effort-keeper.sh` | supervise the sweep watcher and progress logger |
| `opus5-redeploy.sh` | redeploy the app with the pinned binary, retrying stalled uploads |

Each script hardcodes the pinned binary path used for that run
(`~/.jcode/scratch/opus5-build/target/release/jcode`, `jcode v0.56.19-dev
(b9b1470ad)`). Update the path and re-pin before reusing them.

`opus5-finish.sh` runs the whole publication pipeline once the matrix is
terminal: the validity gate, the result reports, and then the website publish
gate, which refuses on its own if the run is unpublishable or jcode did not win.

## Reading progress correctly

Opus 5 turns on these tasks are very large: observed sizes include 46,878,
55,675, 65,291, 78,077, and **84,966** output tokens in a single turn. At
streaming rates that is tens of minutes with no new log lines and no new score,
so a cell can look hung for 40 minutes while working normally.

Three separate times a cell that appeared frozen resumed on its own. Before
concluding a cell is stuck, check that the agent log byte count is still growing
over a span longer than the largest plausible turn, and remember that the score
curve only moves when the agent runs `./grade`.

## Grade count is not a progress metric

The two harnesses use different strategies, both legitimate:

- Claude Code edits, grades, reads the score, and repeats. It logged 63 grades on
  `json-unescape` inside 73 minutes.
- jcode front-loads reasoning: on `float-print` it spent its first 70 minutes
  deriving Schubfach log-approximation constants and generating and validating
  lookup tables in Python before writing any C, with the baseline grade as its
  only score.

So a low grade count early in a run does not mean a cell is unproductive, and a
high grade count does not mean better work. Only the final official grade is
comparable. This is the same trap as reading a frozen score curve as a stall,
and it is why the 20-hour budget matters: judging jcode at 70 minutes would
misrepresent it exactly the way the original truncated run did.

## Supervision

`opus5-bench-watch.service` is the reliable entry point:

```bash
cp modal/scripts/opus5-bench-watch.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now opus5-bench-watch.service
```

Shell-level supervision was not enough. `setsid` survived a harness reload, but
the keeper itself kept dying whenever the shell that spawned it was replaced,
which silently left a 20-hour matrix unobserved. systemd restarts the keeper,
and the keeper restarts the watcher and progress logger.

The keeper exists because `setsid` alone was not enough: killing the shell that
had spawned a watcher also took the watcher down mid-run. The keeper polls every
two minutes, relaunches `opus5-finish.sh` if it is missing, and stops once
`REPORTS_WRITTEN` appears in the finisher log.

Logs land at `/tmp/opus5-run.log`, `/tmp/opus5-cc.log`,
`/tmp/opus5-monitor.log`, and `/tmp/opus5-finish.log`.

## Effort sweep supervision

The sweep has its own watcher chain so it cannot collide with a head-to-head run
still being supervised: separate logs, separate PID directory, separate systemd
unit, and a manifest passed as an argument instead of hardcoded.

```bash
cp modal/scripts/opus5-effort-watch.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now opus5-effort-watch.service
```

The sweep finisher deliberately stops after the validity gate and the reports. It
does not run the website payload builder, because that builder encodes a
two-harness head-to-head claim and a three-effort sweep would need a gate that
understands the extra axis before it could be published.

Logs: `/tmp/opus5-effort-sweep.log`, `/tmp/opus5-effort-finish.log`,
`/tmp/opus5-effort-progress.log`, `/tmp/opus5-effort-keeper.log`.
