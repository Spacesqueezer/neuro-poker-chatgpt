from poker.cards.card import Card


class Hand:
	def __init__(self, cards=None):
		self.cards = list(cards or [])

		if len(self.cards) > 2:
			raise ValueError("Texas Hold'em hand cannot contain more than two cards")

	def add_card(self, card: Card):
		if len(self.cards) >= 2:
			raise ValueError("Hand is full")

		self.cards.append(card)

	def is_complete(self):
		return len(self.cards) == 2
