import random

from poker.cards.card import Card
from poker.enums import Rank, Suit


class Deck:
	def __init__(self):
		self.cards = []
		self.reset()

	def reset(self):
		self.cards = [
			Card(rank, suit)
			for suit in Suit
			for rank in Rank
		]

	def shuffle(self):
		random.shuffle(self.cards)

	def draw(self):
		if not self.cards:
			raise RuntimeError("Deck is empty")

		return self.cards.pop()
