import json
from pathlib import Path

from poker.solver.evaluation import validate_policy_game_compatibility
from poker.solver.export import (
	StrategyLookup,
	information_set_key,
	serialize_information_set,
	validate_strategy_export,
)


TEACHER_RECORD_FORMAT_VERSION = 1


def build_teacher_record_export(payload, game):
	validate_strategy_export(payload)
	validate_policy_game_compatibility(payload, game)

	lookup = StrategyLookup(payload)
	records = {}
	missing_information_sets = set()
	zero_overlap_information_sets = set()

	def traverse(state):
		if game.is_terminal_node(state):
			return

		player = game.player_to_act(state)
		legal_actions = tuple(game.legal_actions(state))
		information_set = game.information_set_for_node(
			state,
			player,
		)
		serialized = serialize_information_set(information_set)
		key = information_set_key(serialized)

		if key not in records:
			stored = lookup.lookup(information_set)
			if stored is None:
				missing_information_sets.add(key)
			else:
				overlap = sum(
					stored.get(action, 0.0)
					for action in legal_actions
				)
				if overlap <= 0.0:
					zero_overlap_information_sets.add(key)
				else:
					action_probabilities = {
						action: stored.get(action, 0.0) / overlap
						for action in legal_actions
					}
					records[key] = {
						"information_set": serialized,
						"legal_actions": list(legal_actions),
						"action_probabilities": action_probabilities,
						"source": (
							"exact"
							if set(stored) == set(legal_actions)
							else "reconciled"
						),
					}

		for action in legal_actions:
			traverse(game.next_node(state, action))

	for initial in game.initial_nodes():
		traverse(initial.state)

	ordered_records = [
		records[key]
		for key in sorted(records)
	]

	return {
		"format_version": TEACHER_RECORD_FORMAT_VERSION,
		"source_strategy": {
			"format_version": payload["format_version"],
			"solver": payload["solver"],
			"iterations": payload["iterations"],
			"seed": payload["seed"],
			"benchmark": payload["benchmark"],
			"action_abstraction": payload["action_abstraction"],
		},
		"record_count": len(ordered_records),
		"skipped_missing_information_sets": len(
			missing_information_sets
		),
		"skipped_zero_overlap_information_sets": len(
			zero_overlap_information_sets
		),
		"records": ordered_records,
	}


def write_teacher_record_export(payload, output):
	path = Path(output)
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(
		json.dumps(
			payload,
			indent=2,
			sort_keys=True,
		) + "\n",
		encoding="utf-8",
	)
