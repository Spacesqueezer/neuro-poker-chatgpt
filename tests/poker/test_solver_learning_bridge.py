import json

import pytest

from poker.statistics.opponent_profile import OpponentProfileEncoder
from poker.solver import (
	MCCFRResult,
	build_learning_bridge_artifact,
	build_learning_bridge_records,
	build_strategy_export,
	build_teacher_record_export,
	load_learning_bridge_artifact,
	validate_learning_bridge_artifact,
	write_learning_bridge_artifact,
)
from tools.benchmark_mccfr import create_benchmark_game


def build_teacher(game, state, strategy, scenario="equal"):
	player = game.player_to_act(state)
	information_set = game.information_set_for_node(
		state,
		player,
	)
	strategy_payload = build_strategy_export(
		MCCFRResult(
			iterations=1,
			average_strategy={
				information_set: strategy,
			},
			cumulative_regret={},
		),
		game,
		seed=42,
		scenario=scenario,
		benchmark_version=2,
	)
	return build_teacher_record_export(
		strategy_payload,
		game,
	)


def test_learning_bridge_contains_only_proven_observation_semantics():
	game = create_benchmark_game("equal")
	root = game.initial_nodes()[0].state
	teacher = build_teacher(
		game,
		root,
		{
			"fold": 0.1,
			"call": 0.2,
			"raise": 0.6,
			"all_in": 0.1,
		},
	)

	record = build_learning_bridge_records(teacher)[0]
	observation = record.observation

	assert observation.player_index == 0
	assert observation.acting_player == "player_0"
	assert observation.opponent_order == ("player_1",)
	assert observation.street == "preflop"
	assert observation.hole_cards == (
		(14, "H"),
		(14, "S"),
	)
	assert observation.public_board == ()
	assert observation.hero_starting_stack == 20
	assert observation.hero_total_contribution == 1
	assert observation.hero_remaining_chips == 19
	assert observation.opponent_starting_stack == 20
	assert observation.opponent_total_contribution == 2
	assert observation.opponent_remaining_chips == 18
	assert observation.opponent_present is True
	assert observation.opponent_folded is False
	assert observation.table_pot == 0
	assert observation.table_target_bet == 2
	assert observation.table_minimum_raise == 2
	assert observation.hero_current_bet == 1
	assert observation.opponent_current_bet == 2
	assert observation.absent_opponent_slots == (
		1,
		2,
		3,
		4,
		5,
		6,
		7,
	)


def test_learning_bridge_preserves_existing_six_category_target():
	game = create_benchmark_game("equal")
	root = game.initial_nodes()[0].state
	teacher = build_teacher(
		game,
		root,
		{
			"fold": 0.1,
			"call": 0.2,
			"raise": 0.6,
			"all_in": 0.1,
		},
	)

	target = build_learning_bridge_records(teacher)[0].target

	assert target.action_names == (
		"fold",
		"check",
		"call",
		"bet",
		"raise",
		"all_in",
	)
	assert target.probabilities == (
		0.1,
		0.0,
		0.2,
		0.0,
		0.6,
		0.1,
	)


def test_learning_bridge_lists_unavailable_production_features_explicitly():
	game = create_benchmark_game("equal")
	root = game.initial_nodes()[0].state
	teacher = build_teacher(
		game,
		root,
		{
			"fold": 1.0,
		},
	)

	record = build_learning_bridge_records(teacher)[0]

	assert record.omitted_production_features == (
		"opponent.0.profile.*",
	)
	assert record.observation.opponent_profile is None
	assert record.observation.table_pot == 0
	assert record.observation.table_target_bet == 2
	assert record.observation.table_minimum_raise == 2
	assert record.observation.hero_current_bet == 1
	assert record.observation.opponent_current_bet == 2


def test_learning_bridge_derives_player_relative_stacks_for_player_one():
	game = create_benchmark_game("equal")
	root = game.initial_nodes()[0].state
	raised = game.next_node(root, "raise")
	teacher = build_teacher(
		game,
		raised,
		{
			"fold": 0.2,
			"call": 0.3,
			"all_in": 0.5,
		},
	)

	observation = build_learning_bridge_records(
		teacher
	)[0].observation

	assert observation.player_index == 1
	assert observation.acting_player == "player_1"
	assert observation.opponent_order == ("player_0",)
	assert observation.hero_starting_stack == 20
	assert observation.hero_total_contribution == 2
	assert observation.hero_remaining_chips == 18
	assert observation.opponent_starting_stack == 20
	assert observation.opponent_total_contribution == 6
	assert observation.opponent_remaining_chips == 14


def test_learning_bridge_artifact_is_deterministic_and_round_trips(tmp_path):
	game = create_benchmark_game("equal")
	root = game.initial_nodes()[0].state
	teacher = build_teacher(
		game,
		root,
		{
			"fold": 0.1,
			"call": 0.2,
			"raise": 0.6,
			"all_in": 0.1,
		},
	)

	first = build_learning_bridge_artifact(teacher)
	second = build_learning_bridge_artifact(teacher)

	assert first == second
	assert first["format_version"] == 3
	assert first["observation_compatibility_version"] == 1
	assert first["opponent_profile_feature_names"] == list(
		OpponentProfileEncoder.FEATURE_NAMES
	)
	assert first["target_actions"] == [
		"fold",
		"check",
		"call",
		"bet",
		"raise",
		"all_in",
	]
	assert first["record_count"] == teacher["record_count"]
	assert first["source_teacher"]["source_strategy"] == teacher[
		"source_strategy"
	]

	output = tmp_path / "bridge.json"
	write_learning_bridge_artifact(first, output)
	assert load_learning_bridge_artifact(output) == first
	assert json.loads(
		output.read_text(encoding="utf-8")
	) == first


def test_learning_bridge_accepts_explicit_encoded_opponent_profiles():
	game = create_benchmark_game("equal")
	root = game.initial_nodes()[0].state
	teacher = build_teacher(game, root, {"fold": 1.0})
	player_0 = tuple(float(index) for index in range(22))
	player_1 = tuple(float(index + 100) for index in range(22))

	record = build_learning_bridge_records(
		teacher,
		opponent_profiles={
			"player_0": player_0,
			"player_1": player_1,
		},
	)[0]

	assert record.observation.opponent_profile == player_1
	assert record.omitted_production_features == ()

	payload = build_learning_bridge_artifact(
		teacher,
		opponent_profiles={
			"player_0": player_0,
			"player_1": player_1,
		},
	)
	assert payload["omitted_production_features"] == []
	assert payload["records"][0]["observation"]["opponent_profile"] == list(player_1)


def test_learning_bridge_rejects_invalid_explicit_opponent_profile_shape():
	game = create_benchmark_game("equal")
	root = game.initial_nodes()[0].state
	teacher = build_teacher(game, root, {"fold": 1.0})

	with pytest.raises(ValueError, match="opponent profile for player_0 is invalid"):
		build_learning_bridge_records(
			teacher,
			opponent_profiles={
				"player_0": (0.0,),
				"player_1": (0.0,) * 22,
			},
		)


def test_learning_bridge_artifact_rejects_omitted_feature_drift():
	game = create_benchmark_game("equal")
	root = game.initial_nodes()[0].state
	teacher = build_teacher(
		game,
		root,
		{
			"fold": 1.0,
		},
	)
	payload = build_learning_bridge_artifact(teacher)
	payload["omitted_production_features"].append(
		"future.fake_feature"
	)

	with pytest.raises(
		ValueError,
		match="omitted production features mismatch",
	):
		validate_learning_bridge_artifact(payload)


def test_learning_bridge_artifact_rejects_probability_corruption():
	game = create_benchmark_game("equal")
	root = game.initial_nodes()[0].state
	teacher = build_teacher(
		game,
		root,
		{
			"fold": 0.1,
			"call": 0.2,
			"raise": 0.6,
			"all_in": 0.1,
		},
	)
	payload = build_learning_bridge_artifact(teacher)
	payload["records"][0]["target"]["probabilities"][0] = 0.5

	with pytest.raises(
		ValueError,
		match="probabilities must sum to 1",
	):
		validate_learning_bridge_artifact(payload)


def test_learning_bridge_artifact_rejects_record_count_mismatch():
	game = create_benchmark_game("equal")
	root = game.initial_nodes()[0].state
	teacher = build_teacher(
		game,
		root,
		{
			"fold": 1.0,
		},
	)
	payload = build_learning_bridge_artifact(teacher)
	payload["record_count"] += 1

	with pytest.raises(
		ValueError,
		match="record_count mismatch",
	):
		validate_learning_bridge_artifact(payload)
