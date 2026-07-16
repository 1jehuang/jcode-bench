from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("collect_matrix.py")
SPEC = importlib.util.spec_from_file_location("collect_matrix", MODULE_PATH)
assert SPEC and SPEC.loader
collect = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collect)


class CollectMatrixTests(unittest.TestCase):
    def make_cell(self, root: Path, task: str, condition: str) -> None:
        cell = root / condition / task
        sessions = cell / "sessions"
        sessions.mkdir(parents=True)
        metadata = {
            "run_id": f"test-{condition}-{task}",
            "bench_commit": "a9bfcdd9ed6cba355bef1025b552ee3da70ce2c0",
            "jcode_version": "test",
            "jcode_sha256": "abc",
            "jcode_config_sha256": "cfg",
            "swarm_prompt_sha256": "prompt",
            "root_session_id": "root",
            "pricing_snapshot": {
                "usd_per_million_tokens": {
                    "openai-api:gpt-5.6-sol": {
                        "input": 5.0,
                        "output": 30.0,
                        "cache_read": 0.5,
                        "cache_write": 6.25,
                    },
                    "claude-api:claude-fable-5": {
                        "input": 10.0,
                        "output": 50.0,
                        "cache_read": 1.0,
                        "cache_write": 12.5,
                    },
                }
            },
        }
        result = {
            **metadata,
            "status": "completed",
            "final_score": 2.0 if condition == "swarm" else 1.0,
            "best_score": 2.0 if condition == "swarm" else 1.0,
            "agent_duration_s": 3600,
        }
        (cell / "metadata.json").write_text(json.dumps(metadata))
        (cell / "result.json").write_text(json.dumps(result))
        (cell / "scores.jsonl").write_text(
            json.dumps({"score": 0.0}) + "\n" + json.dumps({"score": result["final_score"]}) + "\n"
        )
        root_session = {
            "id": "root",
            "parent_id": None,
            "model": "gpt-5.6-sol",
            "provider_key": "openai",
            "reasoning_effort": "high",
            "messages": [
                {
                    "role": "assistant",
                    "token_usage": {
                        "input_tokens": 1000,
                        "output_tokens": 100,
                        "cache_read_input_tokens": 200,
                    },
                }
            ],
        }
        (sessions / "session_root.json").write_text(json.dumps(root_session))
        (sessions / "session_root.journal.jsonl").write_text(
            json.dumps(
                {
                    "append_messages": [
                        {
                            "role": "assistant",
                            "token_usage": {
                                "input_tokens": 1000,
                                "output_tokens": 100,
                                "cache_read_input_tokens": 200,
                            },
                        }
                    ]
                }
            )
            + "\n"
        )
        if condition == "swarm":
            manager = {
                "id": "manager",
                "parent_id": None,
                "model": "claude-api:claude-fable-5",
                "provider_key": "anthropic",
                "reasoning_effort": "low",
                "messages": [
                    {
                        "role": "assistant",
                        "token_usage": {
                            "input_tokens": 500,
                            "output_tokens": 50,
                            "cache_read_input_tokens": 1000,
                            "cache_creation_input_tokens": 100,
                        },
                    }
                ],
            }
            worker = {
                "id": "worker",
                "parent_id": None,
                "model": "openai-api:gpt-5.6-sol",
                "provider_key": "openai",
                "reasoning_effort": "high",
                "messages": [],
            }
            (sessions / "session_manager.json").write_text(json.dumps(manager))
            (sessions / "session_worker.json").write_text(json.dumps(worker))
            state = cell / "state" / "swarm"
            state.mkdir(parents=True)
            (state / "test.json").write_text(
                json.dumps(
                    {
                        "coordinator_session_id": "root",
                        "members": [
                            {"session_id": "root", "role": "coordinator", "report_back_to_session_id": None},
                            {"session_id": "manager", "role": "agent", "report_back_to_session_id": "root"},
                            {"session_id": "worker", "role": "agent", "report_back_to_session_id": "manager"},
                        ],
                    }
                )
            )

    def test_valid_matrix_and_pair_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for condition in collect.CONDITIONS:
                for task in collect.TASKS:
                    self.make_cell(root, task, condition)
            rows = [
                collect.analyze_cell(root, task, condition)
                for condition in collect.CONDITIONS
                for task in collect.TASKS
            ]
            summary = collect.summarize(rows)
            self.assertTrue(summary["all_cells_valid"])
            self.assertEqual(summary["complete_cells"], 6)
            self.assertEqual(summary["swarm_wins"], 3)
            self.assertEqual(summary["mean_score_delta"], 1.0)
            swarm = next(row for row in rows if row["condition"] == "swarm")
            self.assertEqual(swarm["helper_count"], 2)
            self.assertIn("claude-api:claude-fable-5@low", swarm["helper_route_effort_counts"])
            self.assertIn("openai-api:gpt-5.6-sol@high", swarm["helper_route_effort_counts"])
            self.assertGreater(swarm["estimated_api_cost_usd"], 0)
            self.assertIn("result.json", swarm["artifact_sha256"])

    def test_swarm_without_sol_worker_fails_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.make_cell(root, collect.TASKS[0], "swarm")
            (root / "swarm" / collect.TASKS[0] / "sessions" / "session_worker.json").unlink()
            row = collect.analyze_cell(root, collect.TASKS[0], "swarm")
            self.assertFalse(row["complete"])
            self.assertIn("swarm run has no Sol worker session", row["issues"])

    def test_cost_matches_split_and_subset_accounting(self) -> None:
        pricing = {
            "usd_per_million_tokens": {
                "openai-api:gpt-5.6-sol": {
                    "input": 5.0,
                    "output": 30.0,
                    "cache_read": 0.5,
                },
                "claude-api:claude-fable-5": {
                    "input": 10.0,
                    "output": 50.0,
                    "cache_read": 1.0,
                    "cache_write": 12.5,
                },
            }
        }
        usage = {
            "openai-api:gpt-5.6-sol": {"input": 1000, "output": 100, "cache_read": 200},
            "claude-api:claude-fable-5": {
                "input": 500,
                "output": 50,
                "cache_read": 1000,
                "cache_write": 100,
            },
        }
        expected = (800 * 5 + 100 * 30 + 200 * 0.5 + 500 * 10 + 50 * 50 + 1000 * 1 + 100 * 12.5) / 1_000_000
        self.assertEqual(collect.estimate_cost(usage, pricing), round(expected, 6))


if __name__ == "__main__":
    unittest.main()
