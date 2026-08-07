from poker.hand.hand import Hand


class Player:
	def __init__(self, name, chips):
		self.name = name
		self.chips = chips
		self.current_bet = 0
		self.folded = False
		self.hand = Hand()

	def bet(self, amount):
		if amount > self.chips:
			raise ValueError("Not enough chips")

		self.chips -= amount
		self.current_bet += amount

	def collect_bet(self):
		amount = self.current_bet
		self.current_bet = 0
		return amount

	def fold(self):
		self.folded = True

	def reset_for_hand(self):
		self.current_bet = 0
		self.folded = False
		self.hand = Hand()
