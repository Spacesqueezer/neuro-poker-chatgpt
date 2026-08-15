from poker.solver import (
	MCCFRResult,
	build_learning_bridge_records,
	build_strategy_export,
	build_teacher_record_export,
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
		"table.pot",
		"table.target_bet",
		"table.minimum_raise",
		"hero.current_bet",
		"opponent.0.current_bet",
		"opponent.0.profile.*",
		"metadata.acting_player",
		"metadata.opponent_order",
	)
	assert not hasattr(record.observation, "pot")
	assert not hasattr(record.observation, "target_bet")
	assert not hasattr(record.observation, "minimum_raise")
	assert not hasattr(record.observation, "hero_current_bet")
	assert not hasattr(record.observation, "opponent_profile")


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
	assert observation.hero_starting_stack == 20
	assert observation.hero_total_contribution == 2
	assert observation.hero_remaining_chips == 18
	assert observation.opponent_starting_stack == 20
	assert observation.opponent_total_contribution == 6
	assert observation.opponent_remaining_chips == 14
