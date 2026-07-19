# Jcode Bench v1: claude-opus-4-8 high

Benchmark commit: `a9bfcdd9ed6cba355bef1025b552ee3da70ce2c0`
Model: `claude-opus-4-8` with `high` reasoning
Completed cells: **3/3**

## Summary

No four-way Codex/Jcode comparison is defined for this manifest.

## Infrastructure note

- Modal preempted the first float-print container after it passed a **7.2954** full gate and reached a **7.2973** best sampled score. The same FunctionCall automatically restarted from scratch.
- The main table reports the successful retry. Preserved preemption evidence is in `modal/runs/2026-07-18-opencode-opus48-float-print-preemption.json` and `modal/runs/2026-07-18-opencode-opus48-float-print-preempted-scores.jsonl`.

## Per-task results

| Agent | Model | Swarm enabled | Task | Final | Best | Agent time | Grades | Explicit helper events |
|---|---|---:|---|---:|---:|---:|---:|---:|
| opencode | claude-opus-4-8 | no | json-unescape | 1.9991 | 1.9991 | 2562.8s | 83 | 0 |
| opencode | claude-opus-4-8 | no | float-print | 7.2040 | 7.2077 | 5715.1s | 33 | 0 |
| opencode | claude-opus-4-8 | no | utf16-transcode | 1.8526 | 1.8638 | 1890.8s | 42 | 0 |

## Aggregate results

| Agent | Model | Swarm enabled | Tasks | Mean final | Mean best | Total agent time | Helper events |
|---|---|---:|---:|---:|---:|---:|---:|
| opencode | claude-opus-4-8 | no | 3 | 3.6852 | 3.6902 | 10168.7s | 0 |

`Swarm enabled` records the harness configuration. `Explicit helper events` counts native helper tool events present in the captured agent log, so an enabled cell can legitimately report zero if the model did not invoke helpers.
