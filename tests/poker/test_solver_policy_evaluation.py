from poker.solver import (
	MCCFRResult,
	RestrictedSolverPolicy,
	StrategyLookup,
	build_strategy_export,
	evaluate_restricted_policy,
	validate_policy_game_compatibility,
)
from tools.benchmark_mccfr import create_benchmark_game


def collect_uniform_strategy(game):
	strategies = {}

	def traverse(state):
		if game.is_terminal_node(state):
			return

		player = game.player_to_act(state)
		information_set = game.information_set_for_node(
			state,
			player,
		)
		legal_actions = tuple(game.legal_actions(state))
		probability = 1.0 / len(legal_actions)
		strategies[information_set] = {
			action: probability
			for action in legal_actions
		}

		for action in legal_actions:
			traverse(game.next_node(state, action))

	for initial in game.initial_nodes():
		traverse(initial.state)

	return strategies


def make_policy(game, strategies, scenario="equal"):
	payload = build_strategy_export(
		MCCFRResult(
			iterations=1,
			average_strategy=strategies,
			cumulative_regret={},
		),
		game,
		seed=42,
		scenario=scenario,
		benchmark_version=2,
	)
	return RestrictedSolverPolicy(
		StrategyLookup(payload)
	)


def test_policy_evaluation_reports_complete_tree_coverage():
	game = create_benchmark_game("equal")
	policy = make_policy(
		game,
		collect_uniform_strategy(game),
	)

	first = evaluate_restricted_policy(game, policy)
	second = evaluate_restricted_policy(game, policy)

	assert first == second
	assert first["decision_nodes"] > 0
	assert first["terminal_nodes"] > 0
	assert first["unique_information_sets"] > 0
	assert first["fallback_nodes"] == 0
	assert first["covered_nodes"] == first["decision_nodes"]
	assert first["coverage_rate"] == 1.0
	assert first["unique_fallback_information_sets"] == 0
	assert first["information_set_coverage_rate"] == 1.0
	assert sum(first["selected_actions"].values()) == first[
		"decision_nodes"
	]


def test_policy_evaluation_reports_missing_information_set_fallbacks():
	game = create_benchmark_game("equal")
	policy = make_policy(game, {})

	report = evaluate_restricted_policy(game, policy)

	assert report["missing_information_set_fallback_nodes"] == report[
		"decision_nodes"
	]
	assert report["fallback_nodes"] == report["decision_nodes"]
	assert report["covered_nodes"] == 0
	assert report["coverage_rate"] == 0.0
	assert report["information_set_coverage_rate"] == 0.0


def test_policy_evaluation_distinguishes_reconciled_action_sets():
	game = create_benchmark_game("equal")
	root = game.initial_nodes()[0].state
	player = game.player_to_act(root)
	information_set = game.information_set_for_node(
		root,
		player,
	)
	policy = make_policy(
		game,
		{
			information_set: {
				"fold": 1.0,
				"obsolete": 0.0,
			},
		},
	)

	report = evaluate_restricted_policy(game, policy)

	assert report["reconciled_action_set_nodes"] > 0
	assert report["missing_information_set_fallback_nodes"] > 0


def test_policy_evaluation_reports_zero_overlap_fallback():
	game = create_benchmark_game("equal")
	root = game.initial_nodes()[0].state
	player = game.player_to_act(root)
	information_set = game.information_set_for_node(
		root,
		player,
	)
	policy = make_policy(
		game,
		{
			information_set: {
				"obsolete": 1.0,
			},
		},
	)

	report = evaluate_restricted_policy(game, policy)

	assert report["zero_overlap_fallback_nodes"] > 0
	assert report["missing_information_set_fallback_nodes"] > 0


def test_policy_evaluation_rejects_incompatible_game_metadata():
	game = create_benchmark_game("equal")
	policy = make_policy(
		game,
		collect_uniform_strategy(game),
	)
	policy.lookup.payload["benchmark"]["starting_stacks"] = [
		10,
		20,
	]

	try:
		validate_policy_game_compatibility(
			policy.lookup.payload,
			game,
		)
	except ValueError as error:
		assert "starting_stacks" in str(error)
	else:
		raise AssertionError(
			"incompatible strategy metadata must fail"
		)
