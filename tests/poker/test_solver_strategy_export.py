import json

from poker.solver import (
	MCCFRResult,
	StrategyLookup,
	build_strategy_export,
	load_strategy_export,
	serialize_information_set,
	validate_strategy_export,
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
	assert first["format_version"] == 2
	assert first["solver"] == "external_sampling_mccfr"
	assert first["benchmark"]["version"] == 2
	assert first["benchmark"]["scenario"] == "asymmetric"
	assert first["benchmark"]["starting_stacks"] == [8, 20]
	assert first["benchmark"]["small_blind"] == 1
	assert first["benchmark"]["big_blind"] == 2
	assert first["benchmark"]["chance_space"]["version"] == 1
	assert first["benchmark"]["chance_space"]["deal_count"] == 1
	assert first["benchmark"]["chance_space"]["probabilities"] == [1.0]
	assert first["benchmark"]["chance_space"]["identity"].startswith(
		"sha256:"
	)
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
	assert load_strategy_export(output) == first


def test_strategy_export_chance_space_identity_tracks_weighted_deals():
	game = create_benchmark_game("weighted_multi")
	root = game.initial_nodes()[0].state
	info_set = game.information_set_for_node(root, player=0)
	payload = build_strategy_export(
		MCCFRResult(
			iterations=1,
			average_strategy={
				info_set: {
					"call": 1.0,
				},
			},
			cumulative_regret={},
		),
		game,
		seed=42,
		scenario="weighted_multi",
		benchmark_version=2,
	)

	chance_space = payload["benchmark"]["chance_space"]

	assert chance_space["version"] == 1
	assert chance_space["deal_count"] == 3
	assert chance_space["probabilities"] == [0.5, 0.3, 0.2]
	assert chance_space["identity"].startswith("sha256:")
	assert len(chance_space["identity"]) == 71


def test_strategy_lookup_resolves_exact_information_set():
	game = create_benchmark_game("asymmetric")
	root = game.initial_nodes()[0].state
	info_set = game.information_set_for_node(root, player=0)
	result = MCCFRResult(
		iterations=7,
		average_strategy={
			info_set: {
				"call": 0.75,
				"raise": 0.25,
			},
		},
		cumulative_regret={},
	)
	payload = build_strategy_export(
		result,
		game,
		seed=42,
		scenario="asymmetric",
		benchmark_version=2,
	)
	lookup = StrategyLookup(payload)

	assert lookup.lookup(info_set) == {
		"call": 0.75,
		"raise": 0.25,
	}


def test_strategy_lookup_returns_none_for_missing_information_set():
	game = create_benchmark_game("asymmetric")
	root = game.initial_nodes()[0].state
	info_set = game.information_set_for_node(root, player=0)
	result = MCCFRResult(
		iterations=7,
		average_strategy={
			info_set: {
				"call": 1.0,
			},
		},
		cumulative_regret={},
	)
	payload = build_strategy_export(
		result,
		game,
		seed=42,
		scenario="asymmetric",
		benchmark_version=2,
	)
	lookup = StrategyLookup(payload)

	other_info_set = game.information_set_for_node(
		game.next_node(root, "call"),
		player=1,
	)

	assert lookup.lookup(other_info_set) is None


def test_strategy_export_validation_rejects_invalid_version():
	game = create_benchmark_game("equal")
	root = game.initial_nodes()[0].state
	info_set = game.information_set_for_node(root, player=0)
	payload = build_strategy_export(
		MCCFRResult(
			iterations=1,
			average_strategy={
				info_set: {
				"call": 1.0,
				},
			},
			cumulative_regret={},
		),
		game,
		seed=42,
		scenario="equal",
		benchmark_version=2,
	)
	payload["format_version"] = 999

	try:
		validate_strategy_export(payload)
	except ValueError as error:
		assert "format_version" in str(error)
	else:
		raise AssertionError("invalid format version must fail validation")


def test_strategy_export_validation_rejects_missing_chance_space():
	game = create_benchmark_game("equal")
	root = game.initial_nodes()[0].state
	info_set = game.information_set_for_node(root, player=0)
	payload = build_strategy_export(
		MCCFRResult(
			iterations=1,
			average_strategy={
				info_set: {
					"call": 1.0,
				},
			},
			cumulative_regret={},
		),
		game,
		seed=42,
		scenario="equal",
		benchmark_version=2,
	)
	del payload["benchmark"]["chance_space"]

	try:
		validate_strategy_export(payload)
	except ValueError as error:
		assert "chance_space" in str(error)
	else:
		raise AssertionError(
			"missing chance space metadata must fail validation"
		)


def test_strategy_export_validation_rejects_duplicate_information_sets():
	game = create_benchmark_game("equal")
	root = game.initial_nodes()[0].state
	info_set = game.information_set_for_node(root, player=0)
	payload = build_strategy_export(
		MCCFRResult(
			iterations=1,
			average_strategy={
				info_set: {
				"call": 1.0,
				},
			},
			cumulative_regret={},
		),
		game,
		seed=42,
		scenario="equal",
		benchmark_version=2,
	)
	payload["average_strategy"].append(
		payload["average_strategy"][0].copy()
	)
	payload["information_set_count"] = 2

	try:
		validate_strategy_export(payload)
	except ValueError as error:
		assert "duplicate" in str(error)
	else:
		raise AssertionError("duplicate information sets must fail validation")


def test_strategy_export_validation_rejects_invalid_probabilities():
	game = create_benchmark_game("equal")
	root = game.initial_nodes()[0].state
	info_set = game.information_set_for_node(root, player=0)
	payload = build_strategy_export(
		MCCFRResult(
			iterations=1,
			average_strategy={
				info_set: {
				"call": 1.0,
				},
			},
			cumulative_regret={},
		),
		game,
		seed=42,
		scenario="equal",
		benchmark_version=2,
	)
	payload["average_strategy"][0]["strategy"] = {
		"call": 0.6,
		"raise": 0.6,
	}

	try:
		validate_strategy_export(payload)
	except ValueError as error:
		assert "sum to 1" in str(error)
	else:
		raise AssertionError("invalid probabilities must fail validation")
