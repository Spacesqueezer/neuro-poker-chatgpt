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

		session.run(self.agents, hands, seed, stats)
		stats.update_players(session.current_stacks(), self.starting_stack)
		return stats
