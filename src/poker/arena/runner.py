from poker.api import play_hand
from poker.arena.session import ArenaSession
from poker.arena.stats import ArenaStats


class ArenaRunner:
	def __init__(self, agents, starting_stack=100):
		if len(agents) < 2:
			raise ValueError("Arena requires at least two agents")
		self.agents = agents
		self.starting_stack = starting_stack

	def run(self, hands, seed=42):
		stats = ArenaStats()
		players = list(self.agents)
		session = ArenaSession.create(players, self.starting_stack)

		for index in range(hands):
			current_seed = seed + index
			try:
				result = play_hand(
					self.agents,
					seed=current_seed,
					starting_stack=self.starting_stack,
					dealer_name=players[index % len(players)],
				)
				session.apply_hand_result(result)
				stats.record_result(current_seed, result)
			except Exception:
				stats.failed_hands += 1

		stats.update_players(session.current_stacks(), self.starting_stack)
		return stats
