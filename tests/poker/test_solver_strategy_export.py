import json

from poker.solver import (
	MCCFRResult,
	build_strategy_export,
	serialize_information_set,
	write_strategy_export,
)
from tools.benchmark_mccfr import create_benchmark_game


def test_information_set_export_contains_only_acting_player_cards():
	game = create_benchmark_game("asymmetric")
	root = game.initial_nodes()[0].state
	info_set = game.information_set_for_node(root, player=0)

	serialized = serialize_information_set(info_set)

	assert serialized["hole_cards"] == [
		{"rank": 14, "suit": "H"},
		{"rank": 14, "suit": "S"},
	]
	assert {"rank": 13, "suit": "H"} not in serialized["hole_cards"]
	assert {"rank": 13, "suit": "S"} not in serialized["hole_cards"]
	assert serialized["public_board"] == []
	assert serialized["starting_stacks"] == [8, 20]


def test_strategy_export_is_deterministic_and_carries_metadata(tmp_path):
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

	first = build_strategy_export(
		result,
		game,
		seed=42,
		scenario="asymmetric",
		benchmark_version=2,
	)
	second = build_strategy_export(
		result,
		game,
		seed=42,
		scenario="asymmetric",
		benchmark_version=2,
	)

	assert first == second
	assert first["format_version"] == 1
	assert first["solver"] == "external_sampling_mccfr"
	assert first["benchmark"] == {
		"version": 2,
		"scenario": "asymmetric",
		"starting_stacks": [8, 20],
		"small_blind": 1,
		"big_blind": 2,
	}
	assert first["action_abstraction"] == {
		"preflop_raise_bb": 3,
		"postflop_bet_sizes_bb": [1, 2],
		"postflop_raise_increment_multiplier": 2,
	}
	assert first["information_set_count"] == 1

	output = tmp_path / "solver" / "strategy.json"
	write_strategy_export(first, output)
	loaded = json.loads(output.read_text(encoding="utf-8"))

	assert loaded == first
