import random

from poker.api import ActionDecision
from poker.game.actions import PlayerAction


class ManiacAgent:
	"""An extremely aggressive agent that always tries to bet, raise, or go all-in."""
	def __init__(self, seed=None):
		self.random = random.Random(seed)

	def choose_action(self, state, legal):
		actions = legal.actions

		# Prefer All-In
		if PlayerAction.ALL_IN in actions and self.random.random() < 0.2:
			return ActionDecision(PlayerAction.ALL_IN)

		# Prefer Raise
		if PlayerAction.RAISE in actions:
			# Raise big
			amount = legal.max_raise_to if self.random.random() < 0.5 else legal.min_raise_to
			return ActionDecision(PlayerAction.RAISE, amount=amount)

		# Prefer Bet
		if PlayerAction.BET in actions:
			amount = legal.max_bet if self.random.random() < 0.5 else legal.min_bet
			return ActionDecision(PlayerAction.BET, amount=amount)

		# Fallbacks
		if PlayerAction.CALL in actions:
			return ActionDecision(PlayerAction.CALL)

		if PlayerAction.CHECK in actions:
			return ActionDecision(PlayerAction.CHECK)

		return ActionDecision(actions[0])
