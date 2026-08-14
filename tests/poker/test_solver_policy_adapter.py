import pytest

from poker.solver import (
	MCCFRResult,
	RestrictedSolverPolicy,
	StrategyLookup,
	build_strategy_export,
)
from tools.benchmark_mccfr import create_benchmark_game


def make_lookup(game, state, strategy):
	player = game.player_to_act(state)
	information_set = game.information_set_for_node(
		state,
		player,
	)
	payload = build_strategy_export(
		MCCFRResult(
			iterations=1,
			average_strategy={
				information_set: strategy,
			},
			cumulative_regret={},
		),
		game,
		seed=42,
		scenario="equal",
		benchmark_version=2,
	)
	return StrategyLookup(payload)


def test_solver_policy_uses_exact_lookup_strategy():
	game = create_benchmark_game("equal")
	root = game.initial_nodes()[0].state
	lookup = make_lookup(
		game,
		root,
		{
			"fold": 0.1,
			"call": 0.2,
			"raise": 0.6,
			"all_in": 0.1,
		},
	)
	policy = RestrictedSolverPolicy(lookup)

	assert policy.strategy_for_node(game, root) == {
		"fold": 0.1,
		"call": 0.2,
		"raise": 0.6,
		"all_in": 0.1,
	}
	assert policy.choose_action(game, root) == "raise"


def test_solver_policy_missing_information_set_falls_back_to_uniform():
	game = create_benchmark_game("equal")
	root = game.initial_nodes()[0].state
	flop = game.next_node(root, "call")
	lookup = make_lookup(
		game,
		root,
		{
			"fold": 0.25,
			"call": 0.25,
			"raise": 0.25,
			"all_in": 0.25,
		},
	)
	policy = RestrictedSolverPolicy(lookup)

	strategy = policy.strategy_for_node(game, flop)

	assert strategy == {
		"check": 1.0 / 3.0,
		"bet_1bb": 1.0 / 3.0,
		"bet_2bb": 1.0 / 3.0,
	}
	assert policy.choose_action(game, flop) == "check"


def test_solver_policy_filters_illegal_actions_and_renormalizes():
	game = create_benchmark_game("equal")
	root = game.initial_nodes()[0].state
	raised = game.next_node(root, "raise")
	lookup = make_lookup(
		game,
		raised,
		{
			"fold": 0.2,
			"call": 0.3,
			"all_in": 0.5,
		},
	)
	payload = lookup.payload
	payload["average_strategy"][0]["strategy"]["illegal"] = 0.5
	payload["average_strategy"][0]["strategy"]["fold"] = 0.1
	payload["average_strategy"][0]["strategy"]["call"] = 0.15
	payload["average_strategy"][0]["strategy"]["all_in"] = 0.25
	lookup = StrategyLookup(payload)
	policy = RestrictedSolverPolicy(lookup)

	assert policy.strategy_for_node(game, raised) == {
		"fold": 0.2,
		"call": 0.3,
		"all_in": 0.5,
	}


def test_solver_policy_zero_legal_overlap_falls_back_to_uniform():
	game = create_benchmark_game("equal")
	root = game.initial_nodes()[0].state
	lookup = make_lookup(
		game,
		root,
		{
			"fold": 1.0,
		},
	)
	lookup._strategies = {
		key: {"missing_action": 1.0}
		for key in lookup._strategies
	}
	policy = RestrictedSolverPolicy(lookup)

	assert policy.strategy_for_node(game, root) == {
		"fold": 0.25,
		"call": 0.25,
		"raise": 0.25,
		"all_in": 0.25,
	}
	assert policy.choose_action(game, root) == "fold"


def test_solver_policy_rejects_terminal_node():
	game = create_benchmark_game("equal")
	root = game.initial_nodes()[0].state
	fold = game.next_node(root, "fold")
	lookup = make_lookup(
		game,
		root,
		{
			"fold": 1.0,
		},
	)
	policy = RestrictedSolverPolicy(lookup)

	with pytest.raises(
		ValueError,
		match="terminal solver node",
	):
		policy.strategy_for_node(game, fold)
