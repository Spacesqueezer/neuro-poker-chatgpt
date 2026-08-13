from poker.arena.session import ArenaSession
from poker.arena.stats import ArenaStats
from poker.statistics.hand_adapter import HandStatisticsAdapter


class ArenaRunner:
	def __init__(
		self,
		agents,
		starting_stack=100,
		statistics_service=None,
		player_ids=None,
		decision_observer=None,
	):
		if len(agents) < 2:
			raise ValueError("Arena requires at least two agents")
		self.agents = agents
		self.starting_stack = starting_stack
		self.statistics_service = statistics_service
		self.player_ids = dict(player_ids or {})
		self.decision_observer = decision_observer
		self.last_statistics_collector = None

	def run(self, hands, seed=42):
		stats = ArenaStats()
		players = list(self.agents)
		session = ArenaSession.create(players, self.starting_stack)
		statistics_adapter = HandStatisticsAdapter()

		session.run(
			self.agents,
			hands,
			seed,
			stats,
			hand_observer=statistics_adapter.process_hand,
			decision_observer=self.decision_observer,
		)
		stats.update_players(session.current_stacks(), self.starting_stack)

		self.last_statistics_collector = statistics_adapter.collector

		if self.statistics_service is not None:
			self.statistics_service.persist_collector(
				statistics_adapter.collector,
				self.player_ids or None,
			)

		return stats
