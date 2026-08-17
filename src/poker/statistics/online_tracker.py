from poker.statistics.database.models import AgentMemoryRecord
from poker.statistics.hand_mapping import HandStatisticsMapper


class OnlineMemoryTracker:
	def __init__(self, statistics_facade, mapper=None):
		self.statistics_facade = statistics_facade
		self.mapper = mapper or HandStatisticsMapper()

	def process_hand(self, hand_history):
		hand_data = self.mapper.map_hand(hand_history)
		players_data = hand_data.get("players", [])

		for agent_data in players_data:
			agent_name = agent_data["name"]
			# Only update memory if the agent is actively observing/playing

			for opponent_data in players_data:
				opponent_name = opponent_data["name"]
				if agent_name == opponent_name:
					continue

				self._update_memory(agent_name, opponent_name, opponent_data)

	def _update_memory(self, agent_id, opponent_name, opponent_data):
		opponent_player = self.statistics_facade.get_player_by_name(opponent_name)
		if opponent_player is None:
			# If the player is not in DB yet, we can't save memory.
			# In a full setup, the player would be resolved/created beforehand.
			return

		opponent_id = opponent_player.id
		memory = self.statistics_facade.get_opponent_memory(agent_id, opponent_id)

		if memory is None:
			memory = AgentMemoryRecord(
				agent_id=agent_id,
				player_id=opponent_id,
			)

		# Simple moving average for estimates
		# For true tracking, we'd need to track raw counters in memory,
		# but since AgentMemoryRecord only stores float estimates and hands_observed,
		# we'll do a simple exponential moving average (EMA) or exact average if we deduce back the counters.
		# Let's do exact average by converting the estimate back to counts.

		# VPIP
		vpip_hands = memory.vpip_estimate * memory.hands_observed
		if opponent_data.get("entered_pot"):
			vpip_hands += 1

		# PFR
		pfr_hands = memory.pfr_estimate * memory.hands_observed
		if opponent_data.get("raised_preflop"):
			pfr_hands += 1

		# Aggression
		# This is aggression factor: aggressive_actions / calls
		# Storing raw counters is better, but since the model forces floats,
		# we'll use a very rough EMA for aggression.
		# For VPIP/PFR we can be exact because denominator is hands_observed.

		memory.hands_observed += 1
		memory.vpip_estimate = vpip_hands / memory.hands_observed
		memory.pfr_estimate = pfr_hands / memory.hands_observed

		# EMA for aggression factor
		current_aggression = 0.0
		agg_actions = opponent_data.get("aggressive_actions", 0)
		calls = opponent_data.get("calls", 0)
		if calls > 0:
			current_aggression = agg_actions / calls
		elif agg_actions > 0:
			current_aggression = float(agg_actions)

		alpha = 0.1 # EMA decay
		if memory.hands_observed == 1:
			memory.aggression_estimate = current_aggression
		else:
			memory.aggression_estimate = (
				alpha * current_aggression + (1 - alpha) * memory.aggression_estimate
			)

		# Update confidence
		memory.confidence = min(1.0, memory.hands_observed / 1000.0)

		self.statistics_facade.save_opponent_memory(memory)
