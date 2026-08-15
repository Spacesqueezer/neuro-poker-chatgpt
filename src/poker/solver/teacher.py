import json
from pathlib import Path

from poker.solver.evaluation import validate_policy_game_compatibility
from poker.solver.export import (
	STRATEGY_EXPORT_VERSION,
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
	validate_teacher_record_export(payload)

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


def load_teacher_record_export(path):
	payload = json.loads(
		Path(path).read_text(encoding="utf-8")
	)
	return validate_teacher_record_export(payload)


def validate_teacher_record_export(payload):
	if not isinstance(payload, dict):
		raise ValueError("teacher record export must be a JSON object")

	if payload.get("format_version") != TEACHER_RECORD_FORMAT_VERSION:
		raise ValueError("unsupported teacher record format_version")

	source_strategy = payload.get("source_strategy")
	_validate_source_strategy_metadata(source_strategy)

	records = payload.get("records")
	if not isinstance(records, list):
		raise ValueError("teacher record records must be a list")

	if payload.get("record_count") != len(records):
		raise ValueError("teacher record record_count mismatch")

	for field in (
		"skipped_missing_information_sets",
		"skipped_zero_overlap_information_sets",
	):
		value = payload.get(field)
		if not isinstance(value, int) or value < 0:
			raise ValueError(
				f"teacher record {field} must be a non-negative integer"
			)

	seen = set()
	for record in records:
		_validate_teacher_record(record)
		key = information_set_key(record["information_set"])
		if key in seen:
			raise ValueError("duplicate teacher information_set")
		seen.add(key)

	return payload


def validate_teacher_record_compatibility(
	teacher_payload,
	strategy_payload,
	game,
):
	validate_teacher_record_export(teacher_payload)
	validate_strategy_export(strategy_payload)
	validate_policy_game_compatibility(strategy_payload, game)

	expected_source = {
		"format_version": strategy_payload["format_version"],
		"solver": strategy_payload["solver"],
		"iterations": strategy_payload["iterations"],
		"seed": strategy_payload["seed"],
		"benchmark": strategy_payload["benchmark"],
		"action_abstraction": strategy_payload["action_abstraction"],
	}
	if teacher_payload["source_strategy"] != expected_source:
		raise ValueError(
			"teacher record source_strategy does not match strategy artifact"
		)

	return teacher_payload


def _validate_source_strategy_metadata(source):
	if not isinstance(source, dict):
		raise ValueError(
			"teacher record source_strategy metadata is required"
		)

	required = {
		"format_version",
		"solver",
		"iterations",
		"seed",
		"benchmark",
		"action_abstraction",
	}
	if set(source) != required:
		raise ValueError(
			"teacher record source_strategy fields mismatch"
		)

	if source["format_version"] != STRATEGY_EXPORT_VERSION:
		raise ValueError(
			"teacher record source strategy format_version is unsupported"
		)

	if not isinstance(source["solver"], str) or not source["solver"]:
		raise ValueError(
			"teacher record source strategy solver is invalid"
		)

	if (
		not isinstance(source["iterations"], int)
		or source["iterations"] <= 0
	):
		raise ValueError(
			"teacher record source strategy iterations must be positive"
		)

	if not isinstance(source["seed"], int):
		raise ValueError(
			"teacher record source strategy seed must be an integer"
		)

	if not isinstance(source["benchmark"], dict):
		raise ValueError(
			"teacher record source strategy benchmark is required"
		)

	if not isinstance(source["action_abstraction"], dict):
		raise ValueError(
			"teacher record source strategy action_abstraction is required"
		)


def _validate_teacher_record(record):
	if not isinstance(record, dict):
		raise ValueError("teacher record entry must be an object")

	required = {
		"information_set",
		"legal_actions",
		"action_probabilities",
		"source",
	}
	if set(record) != required:
		raise ValueError("teacher record entry fields mismatch")

	if record["source"] not in {"exact", "reconciled"}:
		raise ValueError("teacher record source is invalid")

	information_set = record["information_set"]
	if not isinstance(information_set, dict):
		raise ValueError(
			"teacher record information_set must be an object"
		)

	legal_actions = record["legal_actions"]
	if (
		not isinstance(legal_actions, list)
		or not legal_actions
		or any(
			not isinstance(action, str) or not action
			for action in legal_actions
		)
		or len(set(legal_actions)) != len(legal_actions)
	):
		raise ValueError(
			"teacher record legal_actions must be unique non-empty strings"
		)

	probabilities = record["action_probabilities"]
	if (
		not isinstance(probabilities, dict)
		or set(probabilities) != set(legal_actions)
	):
		raise ValueError(
			"teacher record action probabilities must match legal_actions"
		)

	for probability in probabilities.values():
		if (
			not isinstance(probability, (int, float))
			or isinstance(probability, bool)
			or probability < 0.0
			or probability > 1.0
		):
			raise ValueError(
				"teacher record probabilities must be between 0 and 1"
			)

	if abs(sum(probabilities.values()) - 1.0) > 1e-9:
		raise ValueError(
			"teacher record probabilities must sum to 1"
		)
