# AWS JcodeBench solo vs swarm matrix

This harness runs all three frozen JcodeBench v1 tasks in two matched conditions:

| Condition | Coordinator | Delegation |
|---|---|---|
| `solo` | GPT-5.6 Sol, OpenAI API, high effort | Disabled and explicitly prohibited |
| `swarm` | GPT-5.6 Sol, OpenAI API, high effort | Claude Fable 5 API manager at low effort, GPT-5.6 Sol API workers at high effort, optional GPT-5.6 Luna API context workers at no effort |

The benchmark inputs are pinned to commit `a9bfcdd9ed6cba355bef1025b552ee3da70ce2c0`.
The remote swarm prompt preserves the local model and effort policy from
`~/.jcode/swarm-prompt.md`. Its local OAuth route labels are deliberately changed
to API routes because ECS receives the requested local OpenAI and Anthropic API
keys through AWS Secrets Manager.

## Experimental design

Launch six independent ECS Fargate tasks, one for every task and condition pair.
Use the same image, task definition, vCPU, memory, storage, wall-clock budget,
benchmark revision, Jcode binary, root model, and reasoning effort for every cell.
The only intended treatment difference is swarm availability and required
delegation.

The swarm result gate requires persisted child-session evidence of both:

- `claude-api:claude-fable-5` at `low` effort;
- `openai-api:gpt-5.6-sol` at `high` effort.

A run with swarm enabled but no real helper sessions is invalid and must be rerun.

## Provider secret

Store both keys in one Secrets Manager JSON secret. Do not place keys directly in
an ECS task definition or launch manifest.

```json
{
  "OPENAI_API_KEY": "...",
  "ANTHROPIC_API_KEY": "..."
}
```

The task role needs `secretsmanager:GetSecretValue` for that secret and write
access to the run prefix in the artifact bucket. The execution role needs the
usual ECR image-pull and CloudWatch Logs permissions.

## Container inputs

Build the Docker image from a temporary context containing:

- `aws/Dockerfile`;
- `aws/runner.py`;
- the exact resolved `jcode` binary;
- `bench.tar.gz`, containing only `harness/` and `tasks/` from the frozen commit.

Record the binary version and SHA-256 in every task override. The runner refuses
unsupported task or condition values.

## Required environment variables

- `TASK`: `json-unescape`, `float-print`, or `utf16-transcode`
- `CONDITION`: `solo` or `swarm`
- `RUN_GROUP`: common immutable run identifier
- `S3_BUCKET`: artifact bucket
- `SECRET_ID`: Secrets Manager secret name or ARN
- `JCODE_VERSION`: exact embedded binary version
- `JCODE_SHA256`: exact embedded binary SHA-256

Optional values include `MODEL` (default `gpt-5.6-sol`),
`REASONING_EFFORT` (default `high`), `BUDGET_SECONDS` (default 43200), and
`SWARM_CONCURRENCY` (default 32).

## Launch

After registering a Fargate task definition for the built image, launch the
whole matrix atomically with `aws/launch_matrix.py`. Supply every usable subnet
with repeated `--subnet` arguments and every task security group with repeated
`--security-group` arguments. For example:

```bash
python aws/launch_matrix.py \
  --cluster "$CLUSTER" \
  --task-definition "$TASK_DEFINITION" \
  --container-name jcode-bench \
  --subnet "$SUBNET" \
  --security-group "$SECURITY_GROUP" \
  --bucket "$S3_BUCKET" \
  --secret-id "$SECRET_ID" \
  --run-group "$RUN_GROUP" \
  --jcode-version "$JCODE_VERSION" \
  --jcode-sha256 "$JCODE_SHA256" \
  --budget-seconds 3600
```

If any cell fails to launch, the launcher stops the cells it created so a
partial matrix does not continue consuming budget. On success it writes a local
launch manifest and uploads the same manifest to the run's S3 prefix.

## Durability and retained data

Every worker independently:

1. copies a pristine frozen task into an isolated work directory;
2. saves the effective Jcode config and both local-source and API-adapted swarm prompts;
3. records ECS task metadata, prompt/config hashes, Jcode hash, and a pricing snapshot;
4. grades the baseline before provider credentials are fetched;
5. runs or resumes one root Jcode session until the fixed deadline;
6. snapshots the submission, scores, root and helper sessions, swarm state, and logs;
7. uploads checkpoints, heartbeats, and artifacts to S3 every five minutes;
8. runs the final grader, including the full gate for `float-print`;
9. uploads `result.json` and a terminal `status.json`.

CloudWatch receives the container stream through the task definition's `awslogs`
driver. S3 remains the authoritative long-term artifact store.

## Collect and compare

After the tasks finish:

```bash
python aws/collect_matrix.py \
  --bucket "$S3_BUCKET" \
  --run-group "$RUN_GROUP"
```

The collector writes `analysis.json` and `analysis.md`. It exits nonzero unless
all six cells completed and the solo/swarm routing gates pass. It reports paired
final-score deltas, duration, session and helper counts, per-route token usage,
estimated API cost from the captured pricing table, ECS identity, and SHA-256 for
every retained artifact.

Run its unit tests with:

```bash
python -m unittest aws/test_collect_matrix.py
```
