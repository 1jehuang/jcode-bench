# AWS 12-hour Jcode solo runner

This image runs one Jcode Bench v1 task on ECS Fargate with GPT-5.6 Sol at
high reasoning and swarm disabled. A supervisor resumes the same Jcode session
when a headless turn exits before the 12-hour deadline.

Durability properties:

- one independent Fargate task per benchmark task;
- five-minute submission, score, transcript, heartbeat, and log uploads to S3;
- CloudWatch logging through the ECS `awslogs` driver;
- API credentials read at runtime from Secrets Manager through a restricted task role;
- baseline grading before the agent starts;
- final grading after the deadline, including `--full` for float-print;
- no dependency on the launcher remaining online after `ecs run-task` returns.

The container expects these environment variables from the ECS task definition:
`TASK`, `RUN_GROUP`, `S3_BUCKET`, `SECRET_ID`, `MODEL`, `REASONING_EFFORT`,
`BUDGET_SECONDS`, `JCODE_VERSION`, and `JCODE_SHA256`.
