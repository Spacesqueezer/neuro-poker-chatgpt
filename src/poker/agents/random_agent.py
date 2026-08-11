import random

from poker.api import ActionDecision


class RandomAgent:
	def __init__(self, seed=None):
		self.random = random.Random(seed)

	def choose_action(self, state, legal):
		return ActionDecision(self.random.choice(legal.actions))
