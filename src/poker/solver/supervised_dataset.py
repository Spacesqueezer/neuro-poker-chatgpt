import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from poker.solver.learning_bridge import bridge_observation_to_numeric


SOLVER_SUPERVISED_SAMPLE_VERSION = 1


@dataclass(frozen=True)
class SolverSupervisedSample:
	version: int
	observation: tuple[float, ...]
	action_names: tuple[str, ...]
	legal_mask: tuple[float, ...]
	probabilities: tuple[float, ...]
	solver_action_groups: tuple[tuple[str, ...], ...]
	acting_player: str
	opponent_order: tuple[str, ...]
	source: str

	def to_dict(self):
		return {
			"version": self.version,
			"observation": list(self.observation),
			"action_names": list(self.action_names),
			"legal_mask": list(self.legal_mask),
			"probabilities": list(self.probabilities),
			"solver_action_groups": [
				list(group)
				for group in self.solver_action_groups
			],
			"acting_player": self.acting_player,
			"opponent_order": list(self.opponent_order),
			"source": self.source,
		}


def bridge_record_to_supervised_sample(record):
	numeric = bridge_observation_to_numeric(record.observation)
	target = record.target

	sample = SolverSupervisedSample(
		version=SOLVER_SUPERVISED_SAMPLE_VERSION,
		observation=numeric.values,
		action_names=target.action_names,
		legal_mask=target.legal_mask,
		probabilities=target.probabilities,
		solver_action_groups=target.solver_action_groups,
		acting_player=numeric.acting_player,
		opponent_order=numeric.opponent_order,
		source=target.source,
	)
	_validate_sample_dict(sample.to_dict(), line_number=None)
	return sample


def build_solver_supervised_samples(records):
	return tuple(
		bridge_record_to_supervised_sample(record)
		for record in records
	)


class SolverSupervisedDatasetWriter:
	def __init__(self, path):
		self.path = Path(path)

	def write(self, sample):
		payload = sample.to_dict()
		_validate_sample_dict(payload, line_number=None)
		self.path.parent.mkdir(parents=True, exist_ok=True)
		with self.path.open("a", encoding="utf-8") as file:
			file.write(
				json.dumps(
					payload,
					ensure_ascii=False,
					separators=(",", ":"),
				)
			)
			file.write("\n")

	def write_many(self, samples):
		count = 0
		for sample in samples:
			self.write(sample)
			count += 1
		return count


class SolverSupervisedDatasetAnalyzer:
	def analyze(self, path):
		path = Path(path)
		total = 0
		versions = Counter()
		observation_sizes = Counter()
		sources = Counter()
		acting_players = Counter()

		with path.open("r", encoding="utf-8") as file:
			for line_number, line in enumerate(file, start=1):
				if not line.strip():
					continue

				payload = json.loads(line)
				_validate_sample_dict(payload, line_number=line_number)

				total += 1
				versions[payload["version"]] += 1
				observation_sizes[len(payload["observation"])] += 1
				sources[payload["source"]] += 1
				acting_players[payload["acting_player"]] += 1

		return {
			"samples": total,
			"versions": dict(sorted(versions.items())),
			"observation_sizes": dict(sorted(observation_sizes.items())),
			"sources": dict(sorted(sources.items())),
			"acting_players": dict(sorted(acting_players.items())),
			"consistent_observation_size": len(observation_sizes) <= 1,
		}


def _validate_sample_dict(payload, line_number):
	prefix = (
		f"Solver supervised dataset line {line_number}"
		if line_number is not None
		else "Solver supervised sample"
	)
	if not isinstance(payload, dict):
		raise ValueError(f"{prefix} must be an object")

	required = {
		"version",
		"observation",
		"action_names",
		"legal_mask",
		"probabilities",
		"solver_action_groups",
		"acting_player",
		"opponent_order",
		"source",
	}
	if set(payload) != required:
		raise ValueError(f"{prefix} fields mismatch")

	if payload["version"] != SOLVER_SUPERVISED_SAMPLE_VERSION:
		raise ValueError(f"{prefix} uses unsupported version")

	observation = payload["observation"]
	if (
		not isinstance(observation, list)
		or not observation
		or any(
			not isinstance(value, (int, float))
			or isinstance(value, bool)
			for value in observation
		)
	):
		raise ValueError(f"{prefix} observation is invalid")

	action_names = payload["action_names"]
	legal_mask = payload["legal_mask"]
	probabilities = payload["probabilities"]
	groups = payload["solver_action_groups"]
	expected_actions = [
		"fold",
		"check",
		"call",
		"bet",
		"raise",
		"all_in",
	]
	if action_names != expected_actions:
		raise ValueError(f"{prefix} action_names mismatch")
	if not (
		isinstance(legal_mask, list)
		and isinstance(probabilities, list)
		and isinstance(groups, list)
		and len(legal_mask) == len(expected_actions)
		and len(probabilities) == len(expected_actions)
		and len(groups) == len(expected_actions)
	):
		raise ValueError(f"{prefix} target vector sizes mismatch")
	if any(value not in {0.0, 1.0} for value in legal_mask):
		raise ValueError(f"{prefix} legal_mask is invalid")
	if any(
		not isinstance(value, (int, float))
		or isinstance(value, bool)
		or value < 0.0
		or value > 1.0
		for value in probabilities
	):
		raise ValueError(f"{prefix} probabilities are invalid")
	if abs(sum(probabilities) - 1.0) > 1e-9:
		raise ValueError(f"{prefix} probabilities must sum to 1")

	for index, group in enumerate(groups):
		if (
			not isinstance(group, list)
			or any(
				not isinstance(action, str) or not action
				for action in group
			)
		):
			raise ValueError(f"{prefix} solver action group is invalid")
		expected_mask = 1.0 if group else 0.0
		if legal_mask[index] != expected_mask:
			raise ValueError(f"{prefix} legal_mask/group mismatch")
		if probabilities[index] > 0.0 and not group:
			raise ValueError(f"{prefix} probability assigned to illegal action")

	if not isinstance(payload["acting_player"], str) or not payload["acting_player"]:
		raise ValueError(f"{prefix} acting_player is invalid")
	if (
		not isinstance(payload["opponent_order"], list)
		or any(
			not isinstance(name, str) or not name
			for name in payload["opponent_order"]
		)
	):
		raise ValueError(f"{prefix} opponent_order is invalid")
	if payload["source"] not in {"exact", "reconciled"}:
		raise ValueError(f"{prefix} source is invalid")
