import json

from poker.solver import (
	MCCFRResult,
	build_strategy_export,
	build_teacher_export,
)
from tools.benchmark_mccfr import create_benchmark_game


def test_build_teacher_export_is_deterministic_and_carries_metadata():
	game = create_benchmark_game("asymmetric")
	root = game.initial_nodes()[0].state
	info_set = game.information_set_for_node(root, player=0)

	result = MCCFRResult(
		iterations=7,
		average_strategy={
			info_set: {
				"raise": 0.25,
				"call": 0.75,
			},
		},
		cumulative_regret={},
	)

	strategy_payload = build_strategy_export(
		result,
		game,
		seed=42,
		scenario="asymmetric",
		benchmark_version=2,
	)

	first = build_teacher_export(strategy_payload, game)
	second = build_teacher_export(strategy_payload, game)

	assert first == second
	assert first["format_version"] == 1
	assert first["benchmark"] == strategy_payload["benchmark"]
	assert first["action_abstraction"] == strategy_payload["action_abstraction"]
	assert first["record_count"] == 1
	assert len(first["records"]) == 1

	record = first["records"][0]
	assert record["legal_actions"] == sorted(["fold", "call", "raise", "all_in"])
	assert record["strategy"] == {
		"call": 0.75,
		"raise": 0.25,
	}

def test_build_teacher_export_renormalizes_and_ignores_fallback_actions():
	game = create_benchmark_game("asymmetric")
	root = game.initial_nodes()[0].state
	info_set = game.information_set_for_node(root, player=0)

	result = MCCFRResult(
		iterations=7,
		average_strategy={
			info_set: {
				"raise": 0.25,
				"call": 0.25,
				"invalid_action": 0.50,
			},
		},
		cumulative_regret={},
	)

	strategy_payload = build_strategy_export(
		result,
		game,
		seed=42,
		scenario="asymmetric",
		benchmark_version=2,
	)

	teacher_payload = build_teacher_export(strategy_payload, game)

	assert teacher_payload["record_count"] == 1
	record = teacher_payload["records"][0]

	assert record["strategy"] == {
		"call": 0.5,
		"raise": 0.5,
	}

def test_build_teacher_export_rejects_missing_information_sets():
	game = create_benchmark_game("asymmetric")
	root = game.initial_nodes()[0].state
	info_set = game.information_set_for_node(root, player=0)

	# We intentionally leave info_set missing from average_strategy,
	# effectively providing an empty strategy payload (no solved states).
	result = MCCFRResult(
		iterations=7,
		average_strategy={},
		cumulative_regret={},
	)

	strategy_payload = build_strategy_export(
		result,
		game,
		seed=42,
		scenario="asymmetric",
		benchmark_version=2,
	)

	teacher_payload = build_teacher_export(strategy_payload, game)

	assert teacher_payload["record_count"] == 0
	assert teacher_payload["records"] == []
