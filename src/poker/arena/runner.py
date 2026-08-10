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
			result = play_hand(
				self.agents,
				seed=seed + index,
				dealer_name=players[index % len(players)],
			)
			stats.hands += 1
			stats.seeds.append(seed + index)
			stats.results.append(result)

		return stats
