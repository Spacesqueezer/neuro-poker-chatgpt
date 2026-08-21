from collections import Counter

from poker.solver.export import (
	chance_space_metadata,
	information_set_key,
	serialize_information_set,
)

POLICY_EVALUATION_VERSION = 1


def validate_policy_game_compatibility(payload, game):
	benchmark = payload["benchmark"]
	abstraction = payload["action_abstraction"]

	if tuple(benchmark["starting_stacks"]) != tuple(
		game.starting_stacks
	):
		raise ValueError(
			"strategy artifact starting_stacks do not match evaluation game"
		)

	if benchmark["small_blind"] != game.small_blind:
		raise ValueError(
			"strategy artifact small_blind does not match evaluation game"
		)

	if benchmark["big_blind"] != game.big_blind:
		raise ValueError(
			"strategy artifact big_blind does not match evaluation game"
		)

	if benchmark["chance_space"] != chance_space_metadata(game):
		raise ValueError(
			"strategy artifact chance_space does not match evaluation game"
		)

	expected_abstraction = {
		"preflop_raise_bb": game.action_abstraction.preflop_raise_bb,
		"postflop_bet_sizes_bb": list(
			game.action_abstraction.postflop_bet_sizes_bb
		),
		"postflop_raise_increment_multiplier": (
			game.action_abstraction
			.postflop_raise_increment_multiplier
		),
	}
	if abstraction != expected_abstraction:
		raise ValueError(
			"strategy artifact action_abstraction does not match evaluation game"
		)


def evaluate_restricted_policy(game, policy):
	validate_policy_game_compatibility(
		policy.lookup.payload,
		game,
	)

	counts = Counter()
	selected_actions = Counter()
	unique_sources = {}
	max_depth = 0

	def traverse(state, depth):
		nonlocal max_depth
		max_depth = max(max_depth, depth)

		if game.is_terminal_node(state):
			counts["terminal_nodes"] += 1
			return

		player = game.player_to_act(state)
		legal_actions = tuple(game.legal_actions(state))
		information_set = game.information_set_for_node(
			state,
			player,
		)
		key = information_set_key(
			serialize_information_set(information_set)
		)
		stored = policy.lookup.lookup(information_set)
		source = _strategy_source(
			stored,
			legal_actions,
		)

		counts["decision_nodes"] += 1
		counts[f"{source}_nodes"] += 1
		unique_sources.setdefault(key, source)

		selected_action = policy.choose_action(game, state)
		selected_actions[selected_action] += 1

		for action in legal_actions:
			traverse(
				game.next_node(state, action),
				depth + 1,
			)

	initial_nodes = game.initial_nodes()
	for initial in initial_nodes:
		traverse(initial.state, 0)

	covered_nodes = (
		counts["exact_action_set_nodes"]
		+ counts["reconciled_action_set_nodes"]
	)
	fallback_nodes = (
		counts["missing_information_set_fallback_nodes"]
		+ counts["zero_overlap_fallback_nodes"]
	)
	unique_counts = Counter(unique_sources.values())
	unique_covered = (
		unique_counts["exact_action_set"]
		+ unique_counts["reconciled_action_set"]
	)
	unique_fallback = (
		unique_counts["missing_information_set_fallback"]
		+ unique_counts["zero_overlap_fallback"]
	)

	return {
		"evaluation_version": POLICY_EVALUATION_VERSION,
		"initial_nodes": len(initial_nodes),
		"stored_information_sets": policy.lookup.payload[
			"information_set_count"
		],
		"decision_nodes": counts["decision_nodes"],
		"terminal_nodes": counts["terminal_nodes"],
		"unique_information_sets": len(unique_sources),
		"exact_action_set_nodes": counts[
			"exact_action_set_nodes"
		],
		"reconciled_action_set_nodes": counts[
			"reconciled_action_set_nodes"
		],
		"missing_information_set_fallback_nodes": counts[
			"missing_information_set_fallback_nodes"
		],
		"zero_overlap_fallback_nodes": counts[
			"zero_overlap_fallback_nodes"
		],
		"covered_nodes": covered_nodes,
		"fallback_nodes": fallback_nodes,
		"coverage_rate": _ratio(
			covered_nodes,
			counts["decision_nodes"],
		),
		"unique_covered_information_sets": unique_covered,
		"unique_fallback_information_sets": unique_fallback,
		"information_set_coverage_rate": _ratio(
			unique_covered,
			len(unique_sources),
		),
		"selected_actions": {
			action: selected_actions[action]
			for action in sorted(selected_actions)
		},
		"max_depth": max_depth,
	}


def _strategy_source(stored, legal_actions):
	if stored is None:
		return "missing_information_set_fallback"

	overlap = sum(
		stored.get(action, 0.0)
		for action in legal_actions
	)
	if overlap <= 0.0:
		return "zero_overlap_fallback"

	if set(stored) == set(legal_actions):
		return "exact_action_set"

	return "reconciled_action_set"


def _ratio(numerator, denominator):
	if denominator == 0:
		return 0.0
	return round(numerator / denominator, 6)
