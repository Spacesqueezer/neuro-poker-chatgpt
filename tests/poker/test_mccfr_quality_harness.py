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
		"weighted_multi": (20, 20),
	}

	equal = create_benchmark_game("equal")
	asymmetric = create_benchmark_game("asymmetric")
	weighted = create_benchmark_game("weighted_multi")

	assert equal.starting_stacks == (20, 20)
	assert asymmetric.starting_stacks == (8, 20)
	assert weighted.starting_stacks == (20, 20)


def test_quality_harness_weighted_multi_uses_explicit_chance_probabilities():
	game = create_benchmark_game("weighted_multi")
	initial_nodes = game.initial_nodes()

	assert len(game.deals) == 3
	assert [deal.weight for deal in game.deals] == [
		5.0,
		3.0,
		2.0,
	]
	assert [
		node.probability
		for node in initial_nodes
	] == [
		0.5,
		0.3,
		0.2,
	]

	first_info = game.information_set_for_node(
		initial_nodes[0].state,
		0,
	)
	second_info = game.information_set_for_node(
		initial_nodes[1].state,
		0,
	)

	assert first_info == second_info


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
		"deal_count": 1,
		"chance_probabilities": [1.0],
		"iterations": 100,
		"seed": 42,
		"information_sets": 123,
	}
	output = tmp_path / "solver" / "baseline.json"

	write_report(report, output)

	assert json.loads(output.read_text(encoding="utf-8")) == report
