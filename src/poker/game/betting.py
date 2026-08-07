from enum import Enum


class BettingAction(Enum):
	FOLD = "fold"
	CHECK = "check"
	CALL = "call"
	BET = "bet"
	RAISE = "raise"
	ALL_IN = "all_in"


class BettingState:
	def __init__(self):
		self.pot = 0
		self.current_bet = 0

	def add_bet(self, amount):
		if amount < 0:
			raise ValueError("Bet cannot be negative")

		self.pot += amount
		self.current_bet += amount

	def collect_player_bet(self, player):
		amount = player.collect_bet()
		self.pot += amount
		return amount

	def reset_round(self):
		self.current_bet = 0
