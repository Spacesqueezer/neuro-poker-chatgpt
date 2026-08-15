import pytest

from poker.solver import (
	MCCFRResult,
	SOLVER_TARGET_ACTIONS,
	build_learning_targets,
	build_strategy_export,
	build_teacher_record_export,
	solver_action_category,
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


def test_solver_action_category_is_stable_and_explicit():
	assert SOLVER_TARGET_ACTIONS == (
		"fold",
		"check",
		"call",
		"bet",
		"raise",
		"all_in",
	)
	assert solver_action_category("fold") == "fold"
	assert solver_action_category("bet_1bb") == "bet"
	assert solver_action_category("bet_2bb") == "bet"
	assert solver_action_category("raise") == "raise"
	assert solver_action_category("all_in") == "all_in"

	with pytest.raises(
		ValueError,
		match="unsupported solver action",
	):
		solver_action_category("bet_half_pot")


def test_learning_target_maps_root_actions_without_production_imports():
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

	targets = build_learning_targets(teacher)
	root_target = next(
		target
		for target in targets
		if target.information_set["street"] == "preflop"
		and target.information_set["history"] == []
	)

	assert root_target.action_names == SOLVER_TARGET_ACTIONS
	assert root_target.legal_mask == (
		1.0,
		0.0,
		1.0,
		0.0,
		1.0,
		1.0,
	)
	assert root_target.probabilities == (
		0.1,
		0.0,
		0.2,
		0.0,
		0.6,
		0.1,
	)
	assert root_target.solver_action_groups == (
		("fold",),
		(),
		("call",),
		(),
		("raise",),
		("all_in",),
	)


def test_learning_target_collapses_bet_sizes_but_preserves_groups():
	game = create_benchmark_game("equal")
	root = game.initial_nodes()[0].state
	flop = game.next_node(root, "call")
	teacher = build_teacher(
		game,
		flop,
		{
			"check": 0.25,
			"bet_1bb": 0.25,
			"bet_2bb": 0.5,
		},
	)

	targets = build_learning_targets(teacher)
	flop_target = next(
		target
		for target in targets
		if target.information_set["street"] == "flop"
		and target.information_set["history"] == ["call"]
	)

	assert flop_target.legal_mask == (
		0.0,
		1.0,
		0.0,
		1.0,
		0.0,
		0.0,
	)
	assert flop_target.probabilities == (
		0.0,
		0.25,
		0.0,
		0.75,
		0.0,
		0.0,
	)
	assert flop_target.solver_action_groups[3] == (
		"bet_1bb",
		"bet_2bb",
	)
	assert sum(flop_target.probabilities) == 1.0


def test_learning_target_keeps_solver_information_set_not_learning_observation():
	game = create_benchmark_game("weighted_multi")
	root = game.initial_nodes()[0].state
	teacher = build_teacher(
		game,
		root,
		{
			"fold": 0.25,
			"call": 0.25,
			"raise": 0.25,
			"all_in": 0.25,
		},
		scenario="weighted_multi",
	)

	target = build_learning_targets(teacher)[0]

	assert set(target.information_set) == {
		"player",
		"hole_cards",
		"street",
		"public_board",
		"history",
		"commitments",
		"starting_stacks",
	}
	assert "observation" not in target.information_set
	assert "features" not in target.information_set
