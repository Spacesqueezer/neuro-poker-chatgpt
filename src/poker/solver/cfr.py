from dataclasses import dataclass
from math import fsum


@dataclass(frozen=True)
class CFRResult:
	iterations: int
	average_strategy: dict
	current_strategy: dict
	cumulative_regret: dict
	average_utility: float


class RegretMatching:
	def strategy(self, regrets):
		positive = {
			action: max(0.0, regret)
			for action, regret in regrets.items()
		}
		total = fsum(positive.values())

		if total <= 0.0:
			probability = 1.0 / len(positive)
			return {
				action: probability
				for action in positive
			}

		return {
			action: regret / total
			for action, regret in positive.items()
		}


class KuhnPokerGame:
	ACTIONS = ("check", "bet")
	CARDS = (0, 1, 2)

	def deals(self):
		return tuple(
			(first, second)
			for first in self.CARDS
			for second in self.CARDS
			if first != second
		)

	def current_player(self, history):
		return len(history) % 2

	def is_terminal(self, history):
		return history in {
			("check", "check"),
			("bet", "check"),
			("bet", "bet"),
			("check", "bet", "check"),
			("check", "bet", "bet"),
		}

	def terminal_utility(self, cards, history, player):
		if not self.is_terminal(history):
			raise ValueError("History is not terminal")

		winner = 0 if cards[0] > cards[1] else 1
		if history in {
			("bet", "check"),
			("check", "bet", "check"),
		}:
			folder = 1 if history == ("bet", "check") else 0
			winner = 1 - folder
			value = 1.0
		else:
			value = (
				2.0
				if "bet" in history
				else 1.0
			)

		return value if winner == player else -value

	def information_set(self, cards, history, player):
		return (player, cards[player], history)


class CFRTrainer:
	def __init__(self, game=None):
		self.game = game or KuhnPokerGame()
		self.regret_matching = RegretMatching()
		self.regret_sum = {}
		self.strategy_sum = {}

	def train(self, iterations):
		if iterations <= 0:
			raise ValueError("iterations must be positive")

		utility = 0.0
		deals = self.game.deals()
		deal_probability = 1.0 / len(deals)

		for _ in range(iterations):
			for cards in deals:
				utility += (
					deal_probability
					* self._cfr(
						cards,
						(),
						(1.0, 1.0),
					)
				)

		average_strategy = {
			info_set: self._normalized_strategy(
				strategy_sum
			)
			for info_set, strategy_sum in self.strategy_sum.items()
		}
		current_strategy = {
			info_set: self.regret_matching.strategy(regrets)
			for info_set, regrets in self.regret_sum.items()
		}

		return CFRResult(
			iterations=iterations,
			average_strategy=average_strategy,
			current_strategy=current_strategy,
			cumulative_regret={
				info_set: dict(regrets)
				for info_set, regrets in self.regret_sum.items()
			},
			average_utility=utility / iterations,
		)

	def _cfr(self, cards, history, reach):
		if self.game.is_terminal(history):
			return self.game.terminal_utility(
				cards,
				history,
				player=0,
			)

		player = self.game.current_player(history)
		info_set = self.game.information_set(
			cards,
			history,
			player,
		)
		regrets = self.regret_sum.setdefault(
			info_set,
			{
				action: 0.0
				for action in self.game.ACTIONS
			},
		)
		strategy = self.regret_matching.strategy(regrets)
		strategy_sum = self.strategy_sum.setdefault(
			info_set,
			{
				action: 0.0
				for action in self.game.ACTIONS
			},
		)

		for action, probability in strategy.items():
			strategy_sum[action] += (
				reach[player]
				* probability
			)

		action_utilities = {}
		node_utility = 0.0

		for action, probability in strategy.items():
			next_reach = list(reach)
			next_reach[player] *= probability
			child_utility = self._cfr(
				cards,
				history + (action,),
				tuple(next_reach),
			)
			action_utility = (
				child_utility
				if player == 0
				else -child_utility
			)
			action_utilities[action] = action_utility
			node_utility += probability * action_utility

		opponent = 1 - player
		for action in self.game.ACTIONS:
			regret = action_utilities[action] - node_utility
			regrets[action] += reach[opponent] * regret

		return node_utility if player == 0 else -node_utility

	def _normalized_strategy(self, strategy_sum):
		total = fsum(strategy_sum.values())
		if total <= 0.0:
			probability = 1.0 / len(strategy_sum)
			return {
				action: probability
				for action in strategy_sum
			}

		return {
			action: value / total
			for action, value in strategy_sum.items()
		}
