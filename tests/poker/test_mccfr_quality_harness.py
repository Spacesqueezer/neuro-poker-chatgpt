import json

import pytest

from tools.benchmark_mccfr import (
	BENCHMARK_SCENARIOS,
	create_benchmark_game,
	run_benchmark,
	strategy_distance,
	write_report,
)


def test_strategy_distance_is_zero_for_equal_strategies():
	strategy = {
		("info",): {
			"fold": 0.25,
			"call": 0.75,
		},
	}

	assert strategy_distance(strategy, strategy) == 0.0


def test_strategy_distance_detects_changed_action_probability():
	first = {
		("info",): {
			"fold": 0.25,
			"call": 0.75,
		},
	}
	second = {
		("info",): {
			"fold": 0.75,
			"call": 0.25,
		},
	}

	assert strategy_distance(first, second) == 0.5


def test_quality_harness_rejects_single_iteration():
	with pytest.raises(
		ValueError,
		match="iterations must be greater than 1",
	):
		run_benchmark(1, 42)


def test_quality_harness_exposes_explicit_stack_scenarios():
	assert BENCHMARK_SCENARIOS == {
		"equal": (20, 20),
		"asymmetric": (8, 20),
	}

	equal = create_benchmark_game("equal")
	asymmetric = create_benchmark_game("asymmetric")

	assert equal.starting_stacks == (20, 20)
	assert asymmetric.starting_stacks == (8, 20)


def test_quality_harness_rejects_unknown_scenario():
	with pytest.raises(
		ValueError,
		match="unknown benchmark scenario",
	):
		create_benchmark_game("missing")


def test_quality_harness_writes_reusable_json_report(tmp_path):
	report = {
		"benchmark_version": 2,
		"scenario": "asymmetric",
		"starting_stacks": [8, 20],
		"iterations": 100,
		"seed": 42,
		"information_sets": 123,
	}
	output = tmp_path / "solver" / "baseline.json"

	write_report(report, output)

	assert json.loads(output.read_text(encoding="utf-8")) == report
