from dataclasses import dataclass

from poker.learning.actions import LearningActionEncoder
from poker.learning.observation import LearningObservationEncoder


LEARNING_SAMPLE_VERSION = 1


@dataclass(frozen=True)
class LearningSample:
	version: int
	observation: tuple[float, ...]
	action_mask: tuple[float, ...]
	action_sizing: tuple[float, ...]
	action_index: int
	action_amount: float
	acting_player: str
	opponent_order: tuple[str, ...]
	reward: float | None = None

	def to_dict(self):
		d = {
			"version": self.version,
			"observation": list(self.observation),
			"action_mask": list(self.action_mask),
			"action_sizing": list(self.action_sizing),
			"action_index": self.action_index,
			"action_amount": self.action_amount,
			"acting_player": self.acting_player,
			"opponent_order": list(self.opponent_order),
		}
		if self.reward is not None:
			d["reward"] = self.reward
		return d


class LearningSampleBuilder:
	def __init__(self, observation_encoder=None, action_encoder=None):
		self.observation_encoder = (
			observation_encoder or LearningObservationEncoder()
		)
		self.action_encoder = action_encoder or LearningActionEncoder()

	def build(
		self,
		hand_state,
		legal_actions,
		decision,
		agent_id=None,
		profile_scope="private",
	):
		observation = self.observation_encoder.encode(
			hand_state,
			agent_id=agent_id,
			profile_scope=profile_scope,
		)
		action_space = self.action_encoder.encode(
			legal_actions,
			hand_state,
		)
		action_index, action_amount = self.action_encoder.target(
			decision,
			legal_actions,
			hand_state,
		)

		return LearningSample(
			version=LEARNING_SAMPLE_VERSION,
			observation=observation.values,
			action_mask=action_space.mask,
			action_sizing=action_space.sizing,
			action_index=action_index,
			action_amount=action_amount,
			acting_player=observation.acting_player,
			opponent_order=observation.opponent_order,
		)
