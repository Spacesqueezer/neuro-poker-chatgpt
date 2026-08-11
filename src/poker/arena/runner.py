from poker.api import play_hand
from poker.arena.stats import ArenaStats


class ArenaRunner:
	def __init__(self, agents):
		if len(agents) < 2:
			raise ValueError("Arena requires at least two agents")
		self.agents = agents

	def run(self, hands, seed=42):
		stats = ArenaStats()
		players = list(self.agents)

		for index in range(hands):
			current_seed = seed + index
			try:
				result = play_hand(
					self.agents,
					seed=current_seed,
					dealer_name=players[index % len(players)],
				)
				stats.record_result(current_seed, result)
			except Exception:
				stats.failed_hands += 1

		return stats
