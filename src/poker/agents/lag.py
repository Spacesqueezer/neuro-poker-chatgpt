import random

from poker.api import ActionDecision
from poker.game.actions import PlayerAction


class LAGAgent:
	"""Loose-Aggressive agent. Plays many hands, frequently bluffs."""
	def __init__(self, seed=None):
		self.random = random.Random(seed)

	def choose_action(self, state, legal):
		actions = legal.actions

		# High frequency of betting/raising (bluffing or value)
		if self.random.random() < 0.6:
			if PlayerAction.RAISE in actions:
				return ActionDecision(PlayerAction.RAISE, amount=legal.min_raise_to)
			if PlayerAction.BET in actions:
				return ActionDecision(PlayerAction.BET, amount=legal.min_bet)

		# Otherwise call or check
		if PlayerAction.CALL in actions and self.random.random() < 0.8:
			return ActionDecision(PlayerAction.CALL)

		if PlayerAction.CHECK in actions:
			return ActionDecision(PlayerAction.CHECK)

		# Rarely fold
		if PlayerAction.FOLD in actions and self.random.random() < 0.2:
			return ActionDecision(PlayerAction.FOLD)

		# Fallback
		if PlayerAction.CALL in actions: return ActionDecision(PlayerAction.CALL)
		if PlayerAction.FOLD in actions: return ActionDecision(PlayerAction.FOLD)
		return ActionDecision(actions[0])
