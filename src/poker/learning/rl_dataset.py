from dataclasses import replace

from poker.learning.sample import LearningSampleBuilder


class RLDatasetCapture:
	def __init__(
		self,
		writer,
		sample_builder=None,
		agent_ids=None,
		profile_scope="private",
		include_players=None,
	):
		self.writer = writer
		self.sample_builder = sample_builder or LearningSampleBuilder()
		self.agent_ids = dict(agent_ids or {})
		self.profile_scope = profile_scope
		self.include_players = (
			set(include_players)
			if include_players is not None
			else None
		)
		self.hand_buffer = []

	def decision_observer(self, hand_state, legal_actions, decision):
		if (
			self.include_players is not None
			and hand_state.acting_player not in self.include_players
		):
			return None

		agent_id = self.agent_ids.get(hand_state.acting_player)
		sample = self.sample_builder.build(
			hand_state,
			legal_actions,
			decision,
			agent_id=agent_id,
			profile_scope=self.profile_scope,
		)

		# Buffer the sample for the current hand
		self.hand_buffer.append(sample)
		return sample

	def hand_observer(self, history):
		if not history.final_stacks:
			self.hand_buffer.clear()
			return

		initial_stacks = {
			p["name"]: p.get("starting_chips", 0) for p in history.players
		}

		# Compute rewards
		# Normalize reward by total chips in the pot maybe? Or just big blinds.
		# For now, let's use raw stack delta.
		rewards = {}
		for player, final_stack in history.final_stacks.items():
			start_stack = initial_stacks.get(player, 0)
			rewards[player] = final_stack - start_stack

		# Flush buffer to writer with rewards
		for sample in self.hand_buffer:
			reward = rewards.get(sample.acting_player, 0)
			updated_sample = replace(sample, reward=reward)
			self.writer.write(updated_sample)

		self.hand_buffer.clear()
