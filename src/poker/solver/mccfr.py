from dataclasses import dataclass
import random


@dataclass(frozen=True)
class MCCFRResult:
	iterations: int
	average_strategy: dict
	cumulative_regret: dict


class ExternalSamplingMCCFR:
	def __init__(self, game, seed=0):
		self.game = game
		self.random = random.Random(seed)
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
		if self.game.is_terminal_node(state):
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

		self.strategy_sum.setdefault(
			info,
			{item: 0.0 for item in actions},
		)

		strategy = self._regret_matching(regrets)

		for action, probability in strategy.items():
			self.strategy_sum[info][action] += probability

		if player != traversing_player:
			action = self.random_choice(strategy)
			return self._traverse(
				self.game.next_node(state, action),
				traversing_player,
			)

		utilities = {}

		for action in actions:
			utilities[action] = self._traverse(
				self.game.next_node(state, action),
				traversing_player,
			)

		expected = sum(
			strategy[action] * value
			for action, value in utilities.items()
		)

		for action, value in utilities.items():
			regrets[action] += (
				self.chance_weight
				* (value - expected)
			)

		return expected

	def _regret_matching(self, regrets):
		positive = {
			action: max(0.0, value)
			for action, value in regrets.items()
		}

		total = sum(positive.values())

		if total == 0.0:
			probability = 1.0 / len(positive)
			return {
				action: probability
				for action in positive
			}

		return {
			action: value / total
			for action, value in positive.items()
		}

	def random_choice(self, strategy):
		return self.random.choices(
			list(strategy.keys()),
			weights=list(strategy.values()),
		)[0]

	def _average_strategy(self):
		result = {}

		for key, value in self.strategy_sum.items():
			total = sum(value.values())

			if total == 0.0:
				result[key] = dict(value)
				continue

			result[key] = {
				action: weight / total
				for action, weight in value.items()
			}

		return result
