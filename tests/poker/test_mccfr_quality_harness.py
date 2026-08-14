import json

import pytest

from tools.benchmark_mccfr import (
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


def test_quality_harness_writes_reusable_json_report(tmp_path):
	report = {
		"benchmark_version": 1,
		"iterations": 100,
		"seed": 42,
		"information_sets": 123,
	}
	output = tmp_path / "solver" / "baseline.json"

	write_report(report, output)

	assert json.loads(output.read_text(encoding="utf-8")) == report
