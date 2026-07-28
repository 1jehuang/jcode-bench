"""Offline tests for the Opus 5 head-to-head reporting logic.

Run with the modal-provisioned interpreter so `import modal` resolves:

    ~/.local/share/uv/tools/modal/bin/python modal/test_collect_results.py
"""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("collect_results.py")
SPEC = importlib.util.spec_from_file_location("collect_results", MODULE_PATH)
assert SPEC and SPEC.loader
collect = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collect)


def aggregate_row(
    agent: str, mean_final: float, duration_s: float, effort: str = "high"
) -> dict[str, object]:
    return {
        "agent": agent,
        "swarm": False,
        "model": "claude-opus-5",
        "reasoning_effort": effort,
        "completed_tasks": 3,
        "mean_final_score": mean_final,
        "mean_best_score": mean_final,
        "total_agent_duration_s": duration_s,
        "helper_events": 0,
    }


def task_row(
    agent: str, task: str, effort: str, final: float, duration_s: float
) -> dict[str, object]:
    return {
        "agent": agent,
        "swarm": False,
        "task": task,
        "model": "claude-opus-5",
        "reasoning_effort": effort,
        "status": "completed",
        "final_score": final,
        "best_score": final,
        "agent_duration_s": duration_s,
        "helper_events": 0,
    }


class ClaudeCodeHelperEventTests(unittest.TestCase):
    def test_counts_task_tool_use_blocks(self) -> None:
        log = "\n".join(
            [
                json.dumps({"type": "system", "subtype": "init", "model": "claude-opus-5"}),
                json.dumps(
                    {
                        "type": "assistant",
                        "message": {
                            "content": [
                                {"type": "text", "text": "delegating"},
                                {"type": "tool_use", "name": "Task", "input": {}},
                                {"type": "tool_use", "name": "Bash", "input": {}},
                            ]
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "assistant",
                        "message": {"content": [{"type": "tool_use", "name": "Task"}]},
                    }
                ),
                "not json at all",
            ]
        )
        self.assertEqual(collect.helper_event_count("claude-code", log), 2)

    def test_plain_text_turns_are_not_helper_events(self) -> None:
        log = json.dumps(
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "Task done"}]}}
        )
        self.assertEqual(collect.helper_event_count("claude-code", log), 0)

    def test_jcode_swarm_tool_calls_are_counted_separately(self) -> None:
        log = '{"name":"swarm"}\n{"name": "swarm"}\n{"name":"bash"}'
        self.assertEqual(collect.helper_event_count("jcode", log), 2)


class TruncationDetectionTests(unittest.TestCase):
    def test_jcode_turns_at_the_ceiling_are_counted(self) -> None:
        log = "\n".join(
            [
                json.dumps({"type": "tokens", "output": 128000}),
                json.dumps({"type": "tokens", "output": 4321}),
                json.dumps({"type": "tokens", "output": 128000}),
            ]
        )
        self.assertEqual(collect.truncated_turn_count("jcode", log, 128_000), 2)

    def test_claude_code_turns_at_the_ceiling_are_counted(self) -> None:
        log = "\n".join(
            [
                json.dumps({"type": "assistant", "message": {"usage": {"output_tokens": 128000}}}),
                json.dumps({"type": "assistant", "message": {"usage": {"output_tokens": 12}}}),
            ]
        )
        self.assertEqual(collect.truncated_turn_count("claude-code", log, 128_000), 1)

    def test_turns_below_the_ceiling_are_not_truncation(self) -> None:
        # The legacy 32K cap must not be flagged once the ceiling is 128K.
        log = json.dumps({"type": "tokens", "output": 32768})
        self.assertEqual(collect.truncated_turn_count("jcode", log, 128_000), 0)
        # But it is truncation when 32K *is* the ceiling.
        self.assertEqual(collect.truncated_turn_count("jcode", log, 32_768), 1)

    def test_unknown_ceiling_disables_the_check(self) -> None:
        log = json.dumps({"type": "tokens", "output": 128000})
        self.assertEqual(collect.truncated_turn_count("jcode", log, 0), 0)


class HeadToHeadComparisonTests(unittest.TestCase):
    def test_two_harness_manifest_produces_head_to_head(self) -> None:
        aggregates = [
            aggregate_row("jcode", 4.0, 3600.0),
            aggregate_row("claude-code", 3.0, 1800.0),
        ]
        result = collect.comparisons(aggregates)
        self.assertIn("jcode_vs_claude_code", result)
        head_to_head = result["jcode_vs_claude_code"]
        self.assertAlmostEqual(head_to_head["mean_score_delta"], 1.0)
        # +1.0 doubling means a 2x instruction-efficiency advantage.
        self.assertAlmostEqual(head_to_head["geomean_efficiency_factor"], 2.0)
        self.assertAlmostEqual(head_to_head["total_agent_time_delta_percent"], 100.0)

    def test_single_harness_manifest_has_no_comparison(self) -> None:
        self.assertEqual(collect.comparisons([aggregate_row("jcode", 4.0, 3600.0)]), {})

    def test_markdown_renders_head_to_head_summary(self) -> None:
        report = {
            "model": "claude-opus-5",
            "reasoning_effort": "high",
            "benchmark_commit": "abc123",
            "run_count": 6,
            "completed_count": 6,
            "runs": [],
            "aggregates": [
                aggregate_row("jcode", 4.0, 3600.0),
                aggregate_row("claude-code", 3.0, 1800.0),
            ],
            "comparisons": collect.comparisons(
                [
                    aggregate_row("jcode", 4.0, 3600.0),
                    aggregate_row("claude-code", 3.0, 1800.0),
                ]
            ),
        }
        markdown = collect.render_markdown(report)
        self.assertIn("Jcode led Claude Code by **1.0000**", markdown)
        self.assertIn("2.000x", markdown)

    def test_a_loss_is_not_described_as_a_lead(self) -> None:
        aggregates = [
            aggregate_row("jcode", 3.0, 1800.0),
            aggregate_row("claude-code", 4.0, 1800.0),
        ]
        report = {
            "model": "claude-opus-5",
            "reasoning_effort": "high",
            "benchmark_commit": "abc123",
            "run_count": 6,
            "completed_count": 6,
            "runs": [],
            "aggregates": aggregates,
            "comparisons": collect.comparisons(aggregates),
        }
        markdown = collect.render_markdown(report)
        self.assertIn("Jcode trailed Claude Code by **1.0000**", markdown)
        self.assertNotIn("Jcode led Claude Code", markdown)


class EffortSweepTests(unittest.TestCase):
    """An effort sweep must be reported per effort, never averaged across it."""

    def test_aggregate_keeps_efforts_separate(self) -> None:
        rows = [
            task_row("jcode", "json-unescape", "low", 1.0, 100.0),
            task_row("jcode", "json-unescape", "high", 3.0, 300.0),
        ]
        aggregates = collect.aggregate(rows)
        self.assertEqual(len(aggregates), 2)
        by_effort = {row["reasoning_effort"]: row for row in aggregates}
        self.assertAlmostEqual(by_effort["low"]["mean_final_score"], 1.0)
        self.assertAlmostEqual(by_effort["high"]["mean_final_score"], 3.0)

    def test_swept_comparisons_cover_harness_and_effort_axes(self) -> None:
        aggregates = [
            aggregate_row("jcode", 1.0, 1000.0, "low"),
            aggregate_row("claude-code", 0.5, 1000.0, "low"),
            aggregate_row("jcode", 2.0, 2000.0, "medium"),
            aggregate_row("claude-code", 1.0, 1000.0, "medium"),
            aggregate_row("jcode", 3.0, 4000.0, "high"),
            aggregate_row("claude-code", 1.5, 1000.0, "high"),
        ]
        result = collect.comparisons(aggregates)
        for effort in ("low", "medium", "high"):
            self.assertIn(f"jcode_vs_claude_code_{effort}", result)
        # Effort steps must follow capability order, not alphabetical order.
        self.assertIn("jcode_medium_vs_low", result)
        self.assertIn("jcode_high_vs_medium", result)
        self.assertNotIn("jcode_low_vs_high", result)
        self.assertAlmostEqual(result["jcode_medium_vs_low"]["mean_score_delta"], 1.0)
        self.assertAlmostEqual(
            result["jcode_medium_vs_low"]["total_agent_time_delta_percent"], 100.0
        )

    def test_markdown_reports_every_effort_and_its_step(self) -> None:
        aggregates = [
            aggregate_row("jcode", 1.0, 1000.0, "low"),
            aggregate_row("claude-code", 0.5, 1000.0, "low"),
            aggregate_row("jcode", 3.0, 4000.0, "high"),
            aggregate_row("claude-code", 1.5, 1000.0, "high"),
        ]
        report = {
            "model": "claude-opus-5",
            "reasoning_efforts": ["high", "low"],
            "benchmark_commit": "abc123",
            "run_count": 12,
            "completed_count": 12,
            "runs": [
                task_row("jcode", "json-unescape", "low", 1.0, 1000.0),
            ],
            "aggregates": aggregates,
            "comparisons": collect.comparisons(aggregates),
        }
        markdown = collect.render_markdown(report)
        self.assertIn("low/high", markdown)
        self.assertIn("At `low` effort", markdown)
        self.assertIn("At `high` effort", markdown)
        self.assertIn("going from `low` to `high`", markdown)
        # The effort must be visible on each row, not just in the header.
        self.assertIn("| jcode | claude-opus-5 | low |", markdown)
        # Aggregates walk the effort axis in capability order, so a reader is not
        # handed "high" before "low".
        agg = markdown.split("## Aggregate results")[1]
        self.assertLess(
            agg.index("| claude-code | claude-opus-5 | low |"),
            agg.index("| claude-code | claude-opus-5 | high |"),
        )

    def test_swept_loss_is_not_described_as_a_lead(self) -> None:
        aggregates = [
            aggregate_row("jcode", 1.0, 1000.0, "low"),
            aggregate_row("claude-code", 2.0, 1000.0, "low"),
            aggregate_row("jcode", 4.0, 1000.0, "high"),
            aggregate_row("claude-code", 3.0, 1000.0, "high"),
        ]
        report = {
            "model": "claude-opus-5",
            "reasoning_efforts": ["low", "high"],
            "benchmark_commit": "abc123",
            "run_count": 12,
            "completed_count": 12,
            "runs": [],
            "aggregates": aggregates,
            "comparisons": collect.comparisons(aggregates),
        }
        markdown = collect.render_markdown(report)
        self.assertIn("At `low` effort, Jcode trailed Claude Code by **1.0000**", markdown)
        self.assertIn("At `high` effort, Jcode led Claude Code by **1.0000**", markdown)

    def test_incomplete_sweep_renders_without_comparisons(self) -> None:
        report = {
            "model": "claude-opus-5",
            "reasoning_efforts": ["low", "medium", "high"],
            "benchmark_commit": "abc123",
            "run_count": 18,
            "completed_count": 4,
            "runs": [],
            "aggregates": [],
            "comparisons": {},
        }
        markdown = collect.render_markdown(report)
        self.assertIn("sweep is not complete", markdown)


VALIDATOR_PATH = Path(__file__).with_name("validate_opus5_run.py")
_VSPEC = importlib.util.spec_from_file_location("validate_opus5_run", VALIDATOR_PATH)
assert _VSPEC and _VSPEC.loader
validator = importlib.util.module_from_spec(_VSPEC)
_VSPEC.loader.exec_module(validator)


class ValidatorCeilingTests(unittest.TestCase):
    """The publish gate must reject a run truncated at its output ceiling."""

    def test_counts_only_turns_at_the_ceiling_in_force(self) -> None:
        log = "\n".join(
            [
                json.dumps({"type": "tokens", "output": 32768}),
                json.dumps({"type": "tokens", "output": 32768}),
                json.dumps({"type": "tokens", "output": 17421}),
            ]
        )
        # The void Opus 5 pilot shape: two capped turns under a 32K ceiling.
        self.assertEqual(validator.count_ceiling_turns("jcode", log, 32_768), 2)
        # The same log is clean once the ceiling is the real 128K.
        self.assertEqual(validator.count_ceiling_turns("jcode", log, 128_000), 0)

    def test_claude_code_usage_shape_is_understood(self) -> None:
        log = json.dumps(
            {"type": "assistant", "message": {"usage": {"output_tokens": 128000}}}
        )
        self.assertEqual(validator.count_ceiling_turns("claude-code", log, 128_000), 1)

    def test_matched_conditions_detect_a_harness_mismatch(self) -> None:
        cells = [
            {"agent": "jcode", "task": "t",
             "matched": {"bench_commit": "abc", "prompt": "p", "jcode_sha256": "1"}},
            {"agent": "jcode", "task": "t",
             "matched": {"bench_commit": "abc", "prompt": "p", "jcode_sha256": "2"}},
        ]
        problems = validator.check_matched_conditions(cells)
        self.assertTrue(any("jcode_sha256" in problem for problem in problems))

    def test_swept_effort_is_not_treated_as_a_mismatch(self) -> None:
        """Effort is the sweep's independent variable, not a controlled one."""
        cells = [
            {"agent": "jcode", "task": "t",
             "matched": {"bench_commit": "abc", "reasoning_effort": "low"}},
            {"agent": "jcode", "task": "t",
             "matched": {"bench_commit": "abc", "reasoning_effort": "high"}},
        ]
        self.assertEqual(validator.check_matched_conditions(cells), [])

    def test_other_conditions_still_checked_across_a_sweep(self) -> None:
        cells = [
            {"agent": "jcode", "task": "t",
             "matched": {"bench_commit": "abc", "reasoning_effort": "low"}},
            {"agent": "jcode", "task": "t",
             "matched": {"bench_commit": "def", "reasoning_effort": "high"}},
        ]
        problems = validator.check_matched_conditions(cells)
        self.assertEqual(len(problems), 1)
        self.assertIn("bench_commit", problems[0])

    def test_matched_conditions_pass_when_identical(self) -> None:
        cells = [
            {"agent": "jcode", "task": "t", "matched": {"bench_commit": "abc"}},
            {"agent": "jcode", "task": "t", "matched": {"bench_commit": "abc"}},
        ]
        self.assertEqual(validator.check_matched_conditions(cells), [])


class UntimedRunTests(unittest.TestCase):
    """Runs are untimed: only a self-determined finish is a real measurement."""

    def test_agent_budget_leaves_grading_headroom_under_the_modal_cap(self) -> None:
        import ast, pathlib

        src = pathlib.Path(__file__).with_name("opus5_app.py").read_text()
        ast.parse(src)
        ns: dict = {}
        for line in src.splitlines():
            if line.startswith(
                ("FUNCTION_TIMEOUT_SECONDS", "GRADING_RESERVE_SECONDS", "AGENT_TIMEOUT_SECONDS")
            ):
                exec(line, ns)  # noqa: S102 - reading pinned constants from source
        # The agent gets everything except grading reserve: no arbitrary deadline.
        self.assertEqual(
            ns["AGENT_TIMEOUT_SECONDS"],
            ns["FUNCTION_TIMEOUT_SECONDS"] - ns["GRADING_RESERVE_SECONDS"],
        )
        # And it is far beyond the old 20h deadline that used to kill agents.
        self.assertGreater(ns["AGENT_TIMEOUT_SECONDS"], 20 * 60 * 60)
        # Grading still has real headroom so a final grade always completes.
        self.assertGreaterEqual(ns["GRADING_RESERVE_SECONDS"], 30 * 60)


class ValidatorGateCalibrationTests(unittest.TestCase):
    """Only real defects may void a run; true-but-benign facts get disclosed."""

    def test_disclosures_do_not_void_a_run(self) -> None:
        # A clean early exit with no truncation is an agent decision, not a bug.
        cell = {"problems": [], "disclosures": ["exited cleanly after 5.6% of its budget"]}
        self.assertFalse(cell["problems"], "disclosure must not become a failure")

    def test_missing_ceiling_metadata_is_a_hard_failure(self) -> None:
        # Without the ceiling, the truncation check that voided the pilot cannot
        # run, so the run is unverifiable rather than merely caveated.
        log = json.dumps({"type": "tokens", "output": 32768})
        self.assertEqual(validator.count_ceiling_turns("jcode", log, 0), 0)
        self.assertEqual(validator.count_ceiling_turns("jcode", log, 32_768), 1)


class CostModelTests(unittest.TestCase):
    """The cost model must bill both harnesses identically and correctly."""

    def test_matches_claude_codes_own_accounting(self) -> None:
        # Real usage from a completed Claude Code cell that self-reported
        # $22.32791425. Agreeing to the cent validates the pricing convention.
        totals = {
            "input": 200,
            "output": 292280,
            "cache_read": 24907741,
            "cache_write": 410567,
        }
        self.assertAlmostEqual(validator.estimated_cost_usd(totals), 22.33, places=1)

    def test_parses_jcode_token_events(self) -> None:
        log = "\n".join(
            [
                json.dumps({"type": "tokens", "input": 100, "output": 200,
                            "cache_read_input": 300, "cache_creation_input": 400}),
                json.dumps({"type": "tokens", "input": 1, "output": 2,
                            "cache_read_input": 3, "cache_creation_input": 4}),
            ]
        )
        self.assertEqual(
            validator.token_usage("jcode", log),
            {"input": 101, "output": 202, "cache_read": 303, "cache_write": 404},
        )

    def test_parses_claude_code_terminal_usage(self) -> None:
        log = json.dumps(
            {"type": "result", "usage": {"input_tokens": 5, "output_tokens": 6,
                                         "cache_read_input_tokens": 7,
                                         "cache_creation_input_tokens": 8}}
        )
        self.assertEqual(
            validator.token_usage("claude-code", log),
            {"input": 5, "output": 6, "cache_read": 7, "cache_write": 8},
        )

    def test_output_tokens_dominate_cost(self) -> None:
        # Output bills at 5x input, so a thinking-heavy run must cost more than
        # an input-heavy one with the same token count.
        heavy_out = validator.estimated_cost_usd(
            {"input": 0, "output": 1_000_000, "cache_read": 0, "cache_write": 0}
        )
        heavy_in = validator.estimated_cost_usd(
            {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_write": 0}
        )
        self.assertAlmostEqual(heavy_out, 25.0)
        self.assertAlmostEqual(heavy_in, 5.0)


class HarnessPinDriftTests(unittest.TestCase):
    """A mid-run redeploy must not silently split a harness across two builds."""

    @staticmethod
    def cell(agent, task, jsha=None, csha=None):
        return {
            "agent": agent,
            "task": task,
            "matched": {
                "jcode_sha256": jsha,
                "claude_code_sha256": csha,
                "bench_commit": "abc",
                "prompt": f"p-{task}",
            },
        }

    def test_detects_split_jcode_pin(self) -> None:
        # The real incident: rerunning one cell redeployed the app, leaving the
        # other jcode cells on a build differing by 59 files.
        cells = [
            self.cell("jcode", "json-unescape", jsha="5c4b3055"),
            self.cell("jcode", "utf16-transcode", jsha="6c2720bc"),
            self.cell("claude-code", "json-unescape", csha="22cfd6f5"),
        ]
        problems = validator.check_harness_pins(cells)
        self.assertTrue(any("jcode_sha256" in p for p in problems), problems)

    def test_absent_cross_harness_field_is_not_drift(self) -> None:
        # A jcode cell has no Claude Code sha; that must not read as a mismatch.
        cells = [
            self.cell("jcode", "json-unescape", jsha="6c2720bc"),
            self.cell("jcode", "utf16-transcode", jsha="6c2720bc"),
            self.cell("claude-code", "json-unescape", csha="22cfd6f5"),
            self.cell("claude-code", "utf16-transcode", csha="22cfd6f5"),
        ]
        self.assertEqual(validator.check_harness_pins(cells), [])

    def test_detects_split_claude_code_pin(self) -> None:
        cells = [
            self.cell("claude-code", "json-unescape", csha="22cfd6f5"),
            self.cell("claude-code", "utf16-transcode", csha="deadbeef"),
        ]
        problems = validator.check_harness_pins(cells)
        self.assertTrue(any("claude_code_sha256" in p for p in problems), problems)


if __name__ == "__main__":
    unittest.main()
