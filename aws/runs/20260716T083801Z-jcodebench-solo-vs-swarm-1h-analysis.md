# JcodeBench solo vs swarm, one-hour AWS matrix

Run group: `20260716T083801Z-jcodebench-solo-vs-swarm-1h`

## Result

Swarm won all three paired tasks. The mean score improvement was **+0.2309 log2 points**, equivalent to **1.1736x instruction efficiency** or **14.79% fewer instructions** than the solo solutions on a geometric-mean basis.

| Task | Solo | Swarm | Score delta | Efficiency factor | Fewer instructions | Helpers |
|---|---:|---:|---:|---:|---:|---:|
| json-unescape | 2.6509 | 2.7966 | +0.1457 | 1.1063x | 9.61% | 14 |
| float-print | 7.9908 | 8.2654 | +0.2746 | 1.2097x | 17.33% | 27 |
| utf16-transcode | 2.9462 | 3.2186 | +0.2724 | 1.2078x | 17.21% | 9 |

All six cells passed the artifact gate and final correctness gate. `float-print` passed the official exhaustive verifier over all `2^32` float patterns in both conditions.

## Cost and scale

Estimated model cost from the captured pricing snapshot:

- Solo total: **$1.010104**
- Swarm total: **$116.173359**
- Incremental swarm cost: **$115.163255**
- Swarm-to-solo cost ratio: **115.0x**

The three swarm cells created 50 helpers and recorded 1,000,153 output tokens. The cost figures are estimates reconstructed from persisted token usage and the run's fixed pricing snapshot, not provider invoices.

## Routing proof

Every swarm cell persisted at least one `claude-api:claude-fable-5` manager at low effort and multiple `openai-api:gpt-5.6-sol` workers at high effort. Every solo cell persisted exactly one root session and no helpers.

The effective AWS prompt preserves the local routing policy while replacing local OAuth route labels with API routes, because the benchmark securely loaded the user's OpenAI and Anthropic API keys from AWS Secrets Manager.

## Reproducibility

- Frozen JcodeBench commit: `a9bfcdd9ed6cba355bef1025b552ee3da70ce2c0`
- Jcode: `jcode v0.48.19-dev (66589859a, dirty)`
- Jcode SHA-256: `767f76be8a03337812bf016b124bed76d4c3345764acaae4a0cca4c1780c4341`
- Runner SHA-256: `527aa1f65574b4e65cc0664e9f57517f736ff95c0c278b8784c99e4690d374cd`
- Image digest: `sha256:af016cbdf8b40ad9668c850695b3d6afe92e040669198d2c58122b9fb9e751ec`
- Effective swarm prompt SHA-256: `2ec10f34ecbf1938c65206e3f6b90bd73395491c3e6aa596ec0a22f6dae97442`
- ECS task definition: `jcode-bench-v1-swarm-compare-1h:3`
- Artifacts retained: 906 files with individual SHA-256 checksums in `analysis.json`
- S3 prefix: `s3://jcode-bench-v1-280196252242-us-east-1/runs/20260716T083801Z-jcodebench-solo-vs-swarm-1h/`

No ECS tasks or services remain running.
