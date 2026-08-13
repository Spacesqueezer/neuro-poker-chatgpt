import random

from poker.api import ActionDecision
from poker.game.actions import PlayerAction


class RandomAgent:
	def __init__(self, seed=None):
		self.random = random.Random(seed)

	def choose_action(self, state, legal):
		action = self.random.choice(legal.actions)

		if action == PlayerAction.BET:
			amount = self.random.randint(
				legal.min_bet,
				legal.max_bet,
			)
			return ActionDecision(action, amount)

		if action == PlayerAction.RAISE:
			amount = self.random.randint(
				legal.min_raise_to,
				legal.max_raise_to,
			)
			return ActionDecision(action, amount)

		return ActionDecision(action)
