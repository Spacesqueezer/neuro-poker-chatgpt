import json
from collections import Counter
from pathlib import Path

from poker.learning.actions import LearningActionEncoder
from poker.learning.sample import LEARNING_SAMPLE_VERSION, LearningSampleBuilder


class LearningDatasetWriter:
	def __init__(self, path):
		self.path = Path(path)

	def write(self, sample):
		self.path.parent.mkdir(parents=True, exist_ok=True)
		with self.path.open("a", encoding="utf-8") as file:
			file.write(
				json.dumps(
					sample.to_dict(),
					ensure_ascii=False,
					separators=(",", ":"),
				)
			)
			file.write("\n")


class LearningDatasetCapture:
	def __init__(
		self,
		writer,
		sample_builder=None,
		agent_ids=None,
		profile_scope="private",
	):
		self.writer = writer
		self.sample_builder = sample_builder or LearningSampleBuilder()
		self.agent_ids = dict(agent_ids or {})
		self.profile_scope = profile_scope
		self.samples_written = 0

	def __call__(self, hand_state, legal_actions, decision):
		agent_id = self.agent_ids.get(hand_state.acting_player)
		sample = self.sample_builder.build(
			hand_state,
			legal_actions,
			decision,
			agent_id=agent_id,
			profile_scope=self.profile_scope,
		)
		self.writer.write(sample)
		self.samples_written += 1
		return sample


class LearningDatasetAnalyzer:
	def analyze(self, path):
		path = Path(path)
		total = 0
		versions = Counter()
		actions = Counter()
		observation_sizes = Counter()
		mask_sizes = Counter()
		sizing_sizes = Counter()
		players = Counter()

		with path.open("r", encoding="utf-8") as file:
			for line_number, line in enumerate(file, start=1):
				if not line.strip():
					continue

				payload = json.loads(line)
				self._validate(payload, line_number)

				total += 1
				versions[payload["version"]] += 1
				actions[payload["action_index"]] += 1
				observation_sizes[len(payload["observation"])] += 1
				mask_sizes[len(payload["action_mask"])] += 1
				sizing_sizes[len(payload["action_sizing"])] += 1
				players[payload["acting_player"]] += 1

		return {
			"samples": total,
			"versions": dict(sorted(versions.items())),
			"actions": {
				LearningActionEncoder.ACTION_NAMES[index]: count
				for index, count in sorted(actions.items())
			},
			"observation_sizes": dict(sorted(observation_sizes.items())),
			"action_mask_sizes": dict(sorted(mask_sizes.items())),
			"action_sizing_sizes": dict(sorted(sizing_sizes.items())),
			"acting_players": dict(sorted(players.items())),
			"consistent_observation_size": len(observation_sizes) <= 1,
			"consistent_action_mask_size": len(mask_sizes) <= 1,
			"consistent_action_sizing_size": len(sizing_sizes) <= 1,
		}

	def _validate(self, payload, line_number):
		required = {
			"version",
			"observation",
			"action_mask",
			"action_sizing",
			"action_index",
			"action_amount",
			"acting_player",
			"opponent_order",
		}
		missing = required - set(payload)
		if missing:
			raise ValueError(
				f"Dataset line {line_number} missing fields: {sorted(missing)}"
			)

		if payload["version"] != LEARNING_SAMPLE_VERSION:
			raise ValueError(
				f"Dataset line {line_number} uses unsupported version: "
				f"{payload['version']}"
			)

		action_index = payload["action_index"]
		if not 0 <= action_index < len(LearningActionEncoder.ACTION_NAMES):
			raise ValueError(
				f"Dataset line {line_number} has invalid action index: {action_index}"
			)

		if len(payload["action_mask"]) != len(LearningActionEncoder.ACTION_NAMES):
			raise ValueError(
				f"Dataset line {line_number} has invalid action mask size"
			)

		if not payload["action_mask"][action_index]:
			raise ValueError(
				f"Dataset line {line_number} target action is masked illegal"
			)
