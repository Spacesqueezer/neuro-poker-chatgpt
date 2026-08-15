import json
from dataclasses import dataclass
from pathlib import Path

from poker.solver.learning_target import (
	SolverLearningTarget,
	build_learning_targets,
)
from poker.solver.observation_compatibility import (
	OBSERVATION_COMPATIBILITY_VERSION,
	build_observation_compatibility_report,
)
from poker.solver.teacher import (
	TEACHER_RECORD_FORMAT_VERSION,
	validate_teacher_record_export,
)


LEARNING_BRIDGE_FORMAT_VERSION = 2


@dataclass(frozen=True)
class SolverBridgeObservation:
	player_index: int
	acting_player: str
	opponent_order: tuple[str, ...]
	street: str
	hole_cards: tuple[tuple[int, str], ...]
	public_board: tuple[tuple[int, str], ...]
	hero_starting_stack: int
	hero_total_contribution: int
	hero_remaining_chips: int
	opponent_starting_stack: int
	opponent_total_contribution: int
	opponent_remaining_chips: int
	opponent_present: bool
	opponent_folded: bool
	table_pot: int
	table_target_bet: int
	table_minimum_raise: int
	hero_current_bet: int
	opponent_current_bet: int
	absent_opponent_slots: tuple[int, ...]


@dataclass(frozen=True)
class SolverLearningBridgeRecord:
	observation: SolverBridgeObservation
	target: SolverLearningTarget
	omitted_production_features: tuple[str, ...]


def build_learning_bridge_records(teacher_payload):
	targets = build_learning_targets(teacher_payload)
	compatibility = build_observation_compatibility_report()
	omitted = compatibility.unavailable_features

	return tuple(
		SolverLearningBridgeRecord(
			observation=_bridge_observation(target),
			target=target,
			omitted_production_features=omitted,
		)
		for target in targets
	)


def build_learning_bridge_artifact(teacher_payload):
	validate_teacher_record_export(teacher_payload)
	records = build_learning_bridge_records(teacher_payload)
	compatibility = build_observation_compatibility_report()

	payload = {
		"format_version": LEARNING_BRIDGE_FORMAT_VERSION,
		"observation_compatibility_version": (
			OBSERVATION_COMPATIBILITY_VERSION
		),
		"target_actions": list(records[0].target.action_names)
		if records
		else [
			"fold",
			"check",
			"call",
			"bet",
			"raise",
			"all_in",
		],
		"omitted_production_features": list(
			compatibility.unavailable_features
		),
		"source_teacher": {
			"format_version": teacher_payload["format_version"],
			"source_strategy": teacher_payload["source_strategy"],
			"record_count": teacher_payload["record_count"],
			"skipped_missing_information_sets": teacher_payload[
				"skipped_missing_information_sets"
			],
			"skipped_zero_overlap_information_sets": teacher_payload[
				"skipped_zero_overlap_information_sets"
			],
		},
		"record_count": len(records),
		"records": [
			_serialize_bridge_record(record)
			for record in records
		],
	}
	return validate_learning_bridge_artifact(payload)


def write_learning_bridge_artifact(payload, output):
	validate_learning_bridge_artifact(payload)
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


def load_learning_bridge_artifact(path):
	payload = json.loads(
		Path(path).read_text(encoding="utf-8")
	)
	return validate_learning_bridge_artifact(payload)


def validate_learning_bridge_artifact(payload):
	if not isinstance(payload, dict):
		raise ValueError(
			"learning bridge artifact must be a JSON object"
		)

	required = {
		"format_version",
		"observation_compatibility_version",
		"target_actions",
		"omitted_production_features",
		"source_teacher",
		"record_count",
		"records",
	}
	if set(payload) != required:
		raise ValueError(
			"learning bridge artifact fields mismatch"
		)

	if payload["format_version"] != LEARNING_BRIDGE_FORMAT_VERSION:
		raise ValueError(
			"unsupported learning bridge format_version"
		)

	if (
		payload["observation_compatibility_version"]
		!= OBSERVATION_COMPATIBILITY_VERSION
	):
		raise ValueError(
			"unsupported observation compatibility version"
		)

	expected_actions = [
		"fold",
		"check",
		"call",
		"bet",
		"raise",
		"all_in",
	]
	if payload["target_actions"] != expected_actions:
		raise ValueError(
			"learning bridge target_actions mismatch"
		)

	expected_omitted = list(
		build_observation_compatibility_report().unavailable_features
	)
	if payload["omitted_production_features"] != expected_omitted:
		raise ValueError(
			"learning bridge omitted production features mismatch"
		)

	_validate_source_teacher(payload["source_teacher"])

	records = payload["records"]
	if not isinstance(records, list):
		raise ValueError(
			"learning bridge records must be a list"
		)
	if payload["record_count"] != len(records):
		raise ValueError(
			"learning bridge record_count mismatch"
		)
	if payload["source_teacher"]["record_count"] != len(records):
		raise ValueError(
			"learning bridge source teacher record_count mismatch"
		)

	for record in records:
		_validate_serialized_bridge_record(
			record,
			expected_actions,
			expected_omitted,
		)

	return payload


def _serialize_bridge_record(record):
	return {
		"observation": {
			"player_index": record.observation.player_index,
			"acting_player": record.observation.acting_player,
			"opponent_order": list(record.observation.opponent_order),
			"street": record.observation.street,
			"hole_cards": [
				list(card)
				for card in record.observation.hole_cards
			],
			"public_board": [
				list(card)
				for card in record.observation.public_board
			],
			"hero_starting_stack": (
				record.observation.hero_starting_stack
			),
			"hero_total_contribution": (
				record.observation.hero_total_contribution
			),
			"hero_remaining_chips": (
				record.observation.hero_remaining_chips
			),
			"opponent_starting_stack": (
				record.observation.opponent_starting_stack
			),
			"opponent_total_contribution": (
				record.observation.opponent_total_contribution
			),
			"opponent_remaining_chips": (
				record.observation.opponent_remaining_chips
			),
			"opponent_present": record.observation.opponent_present,
			"opponent_folded": record.observation.opponent_folded,
			"table_pot": record.observation.table_pot,
			"table_target_bet": record.observation.table_target_bet,
			"table_minimum_raise": (
				record.observation.table_minimum_raise
			),
			"hero_current_bet": record.observation.hero_current_bet,
			"opponent_current_bet": (
				record.observation.opponent_current_bet
			),
			"absent_opponent_slots": list(
				record.observation.absent_opponent_slots
			),
		},
		"target": {
			"action_names": list(record.target.action_names),
			"legal_mask": list(record.target.legal_mask),
			"probabilities": list(record.target.probabilities),
			"solver_action_groups": [
				list(group)
				for group in record.target.solver_action_groups
			],
			"source": record.target.source,
		},
		"omitted_production_features": list(
			record.omitted_production_features
		),
	}


def _validate_source_teacher(source_teacher):
	if not isinstance(source_teacher, dict):
		raise ValueError(
			"learning bridge source_teacher is required"
		)

	required = {
		"format_version",
		"source_strategy",
		"record_count",
		"skipped_missing_information_sets",
		"skipped_zero_overlap_information_sets",
	}
	if set(source_teacher) != required:
		raise ValueError(
			"learning bridge source_teacher fields mismatch"
		)

	if (
		source_teacher["format_version"]
		!= TEACHER_RECORD_FORMAT_VERSION
	):
		raise ValueError(
			"learning bridge source teacher format_version mismatch"
		)

	if not isinstance(source_teacher["source_strategy"], dict):
		raise ValueError(
			"learning bridge source strategy metadata is required"
		)

	for field in (
		"record_count",
		"skipped_missing_information_sets",
		"skipped_zero_overlap_information_sets",
	):
		value = source_teacher[field]
		if not isinstance(value, int) or value < 0:
			raise ValueError(
				f"learning bridge source teacher {field} is invalid"
			)


def _validate_serialized_bridge_record(
	record,
	expected_actions,
	expected_omitted,
):
	if not isinstance(record, dict):
		raise ValueError(
			"learning bridge record must be an object"
		)
	if set(record) != {
		"observation",
		"target",
		"omitted_production_features",
	}:
		raise ValueError(
			"learning bridge record fields mismatch"
		)

	if record["omitted_production_features"] != expected_omitted:
		raise ValueError(
			"learning bridge record omitted features mismatch"
		)

	_validate_serialized_bridge_observation(record["observation"])
	_validate_serialized_bridge_target(
		record["target"],
		expected_actions,
	)


def _validate_serialized_bridge_observation(observation):
	required = {
		"player_index",
		"acting_player",
		"opponent_order",
		"street",
		"hole_cards",
		"public_board",
		"hero_starting_stack",
		"hero_total_contribution",
		"hero_remaining_chips",
		"opponent_starting_stack",
		"opponent_total_contribution",
		"opponent_remaining_chips",
		"opponent_present",
		"opponent_folded",
		"table_pot",
		"table_target_bet",
		"table_minimum_raise",
		"hero_current_bet",
		"opponent_current_bet",
		"absent_opponent_slots",
	}
	if not isinstance(observation, dict) or set(observation) != required:
		raise ValueError(
			"learning bridge observation fields mismatch"
		)

	if observation["player_index"] not in {0, 1}:
		raise ValueError(
			"learning bridge player_index is invalid"
		)
	expected_acting_player = f"player_{observation['player_index']}"
	expected_opponent_order = [
		f"player_{1 - observation['player_index']}"
	]
	if observation["acting_player"] != expected_acting_player:
		raise ValueError(
			"learning bridge acting_player metadata mismatch"
		)
	if observation["opponent_order"] != expected_opponent_order:
		raise ValueError(
			"learning bridge opponent_order metadata mismatch"
		)
	if observation["street"] not in {
		"preflop",
		"flop",
		"turn",
		"river",
	}:
		raise ValueError(
			"learning bridge street is invalid"
		)

	_validate_serialized_cards(
		observation["hole_cards"],
		expected_count=2,
	)
	_validate_serialized_cards(
		observation["public_board"],
		expected_count=None,
	)

	for prefix in ("hero", "opponent"):
		starting = observation[f"{prefix}_starting_stack"]
		contribution = observation[
			f"{prefix}_total_contribution"
		]
		remaining = observation[f"{prefix}_remaining_chips"]
		if (
			not isinstance(starting, int)
			or starting <= 0
			or not isinstance(contribution, int)
			or contribution < 0
			or contribution > starting
			or not isinstance(remaining, int)
			or remaining != starting - contribution
		):
			raise ValueError(
				f"learning bridge {prefix} stack accounting is invalid"
			)

	if observation["opponent_present"] is not True:
		raise ValueError(
			"learning bridge heads-up opponent must be present"
		)
	if observation["opponent_folded"] is not False:
		raise ValueError(
			"learning bridge live decision opponent cannot be folded"
		)

	for field in (
		"table_pot",
		"table_target_bet",
		"hero_current_bet",
		"opponent_current_bet",
	):
		if not isinstance(observation[field], int) or observation[field] < 0:
			raise ValueError(
				f"learning bridge {field} is invalid"
			)

	if observation["table_target_bet"] != max(
		observation["hero_current_bet"],
		observation["opponent_current_bet"],
	):
		raise ValueError(
			"learning bridge target bet mismatch"
		)
	if (
		not isinstance(observation["table_minimum_raise"], int)
		or observation["table_minimum_raise"] <= 0
	):
		raise ValueError(
			"learning bridge table_minimum_raise is invalid"
		)

	if observation["absent_opponent_slots"] != list(range(1, 8)):
		raise ValueError(
			"learning bridge absent opponent slots mismatch"
		)


def _validate_serialized_cards(cards, expected_count):
	if not isinstance(cards, list):
		raise ValueError(
			"learning bridge cards must be a list"
		)
	if expected_count is not None and len(cards) != expected_count:
		raise ValueError(
			"learning bridge card count mismatch"
		)
	if len(cards) > 5:
		raise ValueError(
			"learning bridge public board is too large"
		)

	for card in cards:
		if (
			not isinstance(card, list)
			or len(card) != 2
			or not isinstance(card[0], int)
			or card[0] < 2
			or card[0] > 14
			or card[1] not in {"C", "D", "H", "S"}
		):
			raise ValueError(
				"learning bridge card is invalid"
			)


def _validate_serialized_bridge_target(target, expected_actions):
	if not isinstance(target, dict):
		raise ValueError(
			"learning bridge target must be an object"
		)
	if set(target) != {
		"action_names",
		"legal_mask",
		"probabilities",
		"solver_action_groups",
		"source",
	}:
		raise ValueError(
			"learning bridge target fields mismatch"
		)

	if target["action_names"] != expected_actions:
		raise ValueError(
			"learning bridge target action_names mismatch"
		)

	legal_mask = target["legal_mask"]
	probabilities = target["probabilities"]
	groups = target["solver_action_groups"]
	if not (
		isinstance(legal_mask, list)
		and isinstance(probabilities, list)
		and isinstance(groups, list)
		and len(legal_mask) == len(expected_actions)
		and len(probabilities) == len(expected_actions)
		and len(groups) == len(expected_actions)
	):
		raise ValueError(
			"learning bridge target vector sizes mismatch"
		)

	if any(value not in {0.0, 1.0} for value in legal_mask):
		raise ValueError(
			"learning bridge legal_mask is invalid"
		)
	if any(
		not isinstance(value, (int, float))
		or isinstance(value, bool)
		or value < 0.0
		or value > 1.0
		for value in probabilities
	):
		raise ValueError(
			"learning bridge probabilities are invalid"
		)
	if abs(sum(probabilities) - 1.0) > 1e-9:
		raise ValueError(
			"learning bridge probabilities must sum to 1"
		)

	for index, group in enumerate(groups):
		if (
			not isinstance(group, list)
			or any(
				not isinstance(action, str) or not action
				for action in group
			)
		):
			raise ValueError(
				"learning bridge solver action group is invalid"
			)
		expected_mask = 1.0 if group else 0.0
		if legal_mask[index] != expected_mask:
			raise ValueError(
				"learning bridge legal_mask/group mismatch"
			)

	if target["source"] not in {"exact", "reconciled"}:
		raise ValueError(
			"learning bridge target source is invalid"
		)


def _bridge_observation(target):
	info = target.information_set
	player = info["player"]
	opponent = 1 - player
	starting_stacks = tuple(info["starting_stacks"])
	commitments = tuple(info["commitments"])

	return SolverBridgeObservation(
		player_index=player,
		acting_player=f"player_{player}",
		opponent_order=(f"player_{opponent}",),
		street=info["street"],
		hole_cards=tuple(
			(card["rank"], card["suit"])
			for card in info["hole_cards"]
		),
		public_board=tuple(
			(card["rank"], card["suit"])
			for card in info["public_board"]
		),
		hero_starting_stack=starting_stacks[player],
		hero_total_contribution=commitments[player],
		hero_remaining_chips=(
			starting_stacks[player] - commitments[player]
		),
		opponent_starting_stack=starting_stacks[opponent],
		opponent_total_contribution=commitments[opponent],
		opponent_remaining_chips=(
			starting_stacks[opponent] - commitments[opponent]
		),
		opponent_present=True,
		opponent_folded=False,
		table_pot=info["collected_pot"],
		table_target_bet=max(info["street_commitments"]),
		table_minimum_raise=info["minimum_raise"],
		hero_current_bet=info["street_commitments"][player],
		opponent_current_bet=info["street_commitments"][opponent],
		absent_opponent_slots=tuple(range(1, 8)),
	)
