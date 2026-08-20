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
		hand_observer=None,
		tournament_mode=False,
	):
		if len(agents) < 2:
			raise ValueError("Arena requires at least two agents")
		self.agents = agents
		self.starting_stack = starting_stack
		self.statistics_service = statistics_service
		self.player_ids = dict(player_ids or {})
		self.decision_observer = decision_observer
		self.hand_observer = hand_observer
		self.tournament_mode = tournament_mode
		self.last_statistics_collector = None

	def run(self, hands, seed=42):
		stats = ArenaStats()
		players = list(self.agents)
		statistics_adapter = HandStatisticsAdapter()

		def composite_hand_observer(history):
			statistics_adapter.process_hand(history)
			if self.hand_observer is not None:
				self.hand_observer(history)

		hands_played = 0
		current_seed = seed

		while hands_played < hands:
			session = ArenaSession.create(players, self.starting_stack, tournament_mode=self.tournament_mode)
			remaining_hands = hands - hands_played

			session.run(
				self.agents,
				remaining_hands,
				current_seed,
				stats,
				hand_observer=composite_hand_observer,
				decision_observer=self.decision_observer,
			)

			for player_name, stack in session.current_stacks().items():
				profit_delta = stack - self.starting_stack
				stats.add_profit(player_name, profit_delta)

			actual_played = session.completed_hands
			# Ensure we advance to prevent infinite loop on catastrophic failures
			advance = actual_played if actual_played > 0 else remaining_hands
			hands_played += advance
			current_seed += advance

			if self.tournament_mode:
				break

		self.last_statistics_collector = statistics_adapter.collector

		if self.statistics_service is not None:
			self.statistics_service.persist_collector(
				statistics_adapter.collector,
				self.player_ids or None,
			)

		return stats
