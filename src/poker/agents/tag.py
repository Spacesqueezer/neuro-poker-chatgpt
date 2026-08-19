import random
from poker.api import ActionDecision
from poker.game.actions import PlayerAction

class TAGAgent:
	"""Tight-Aggressive agent. Plays tight preflop, aggressive postflop if holding a pair or better."""
	def __init__(self, seed=None):
		self.random = random.Random(seed)

	def choose_action(self, state, legal):
		actions = legal.actions
		ranks = [card[:-1] for card in state.hole_cards]

		# Simplistic evaluation for testing/benchmark
		is_pair = len(ranks) == 2 and ranks[0] == ranks[1]
		is_broadway = all(r in ('10', 'J', 'Q', 'K', 'A') for r in ranks)

		is_strong = is_pair or is_broadway

		if state.street == "preflop":
			if not is_strong:
				if PlayerAction.CHECK in actions:
					return ActionDecision(PlayerAction.CHECK)
				if PlayerAction.FOLD in actions:
					return ActionDecision(PlayerAction.FOLD)

			# If strong, try to raise or bet
			if PlayerAction.RAISE in actions:
				return ActionDecision(PlayerAction.RAISE, amount=legal.min_raise_to)
			if PlayerAction.BET in actions:
				return ActionDecision(PlayerAction.BET, amount=legal.min_bet)
			if PlayerAction.CALL in actions:
				return ActionDecision(PlayerAction.CALL)

		else:
			# Postflop: check/fold if weak facing a bet, bet/raise if strong
			if not is_strong:
				if PlayerAction.CHECK in actions:
					return ActionDecision(PlayerAction.CHECK)
				if PlayerAction.FOLD in actions:
					return ActionDecision(PlayerAction.FOLD)
			else:
				if PlayerAction.BET in actions:
					return ActionDecision(PlayerAction.BET, amount=legal.min_bet)
				if PlayerAction.CALL in actions:
					return ActionDecision(PlayerAction.CALL)

		# Safe fallback
		if PlayerAction.CHECK in actions:
			return ActionDecision(PlayerAction.CHECK)
		if PlayerAction.FOLD in actions:
			return ActionDecision(PlayerAction.FOLD)

		return ActionDecision(actions[0])
