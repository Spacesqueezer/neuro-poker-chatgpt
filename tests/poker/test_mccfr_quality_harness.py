import pytest

from tools.benchmark_mccfr import run_benchmark, strategy_distance


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
