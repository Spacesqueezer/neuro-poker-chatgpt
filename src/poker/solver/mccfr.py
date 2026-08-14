from dataclasses import dataclass


@dataclass(frozen=True)
class MCCFRResult:
	iterations: int
	average_strategy: dict
	cumulative_regret: dict


class ExternalSamplingMCCFR:
	def __init__(self, game, seed=0):
		self.game = game
		self.seed = seed
		self.regret_sum = {}
		self.strategy_sum = {}
		self.chance_weight = 1.0

	def train(self, iterations):
		if iterations <= 0:
			raise ValueError("iterations must be positive")

		for _ in range(iterations):
			for node in self.game.initial_nodes():
				self.chance_weight = node.probability
				self._traverse(node.state, 0)

		return MCCFRResult(
			iterations=iterations,
			average_strategy=self._average_strategy(),
			cumulative_regret={
				key: dict(value)
				for key, value in self.regret_sum.items()
			},
		)

	def _traverse(self, state, traversing_player):
		if self.game.is_terminal(state):
			return self.game.terminal_node_utility(
				state,
				traversing_player,
			)

		player = self.game.player_to_act(state)
		info = self.game.information_set_for_node(
			state,
			player,
		)

		actions = self.game.legal_actions(state)
		regrets = self.regret_sum.setdefault(
			info,
			{action: 0.0 for action in actions},
		)

		for action in actions:
			self.strategy_sum.setdefault(
				info,
				{item: 0.0 for item in actions},
			)
			break

		return 0.0

	def _average_strategy(self):
		return {
			key: dict(value)
			for key, value in self.strategy_sum.items()
		}
