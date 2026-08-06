from poker.cards.card import Card


class Board:
	def __init__(self, cards=None):
		self.cards = list(cards or [])

		if len(self.cards) > 5:
			raise ValueError("Texas Hold'em board cannot contain more than five cards")

	def add_card(self, card: Card):
		if len(self.cards) >= 5:
			raise ValueError("Board is full")

		self.cards.append(card)

	def is_complete(self):
		return len(self.cards) == 5

	def flop_ready(self):
		return len(self.cards) >= 3
