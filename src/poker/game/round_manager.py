from enum import Enum


class GameStreet(Enum):
	PREFLOP = "preflop"
	FLOP = "flop"
	TURN = "turn"
	RIVER = "river"
	SHOWDOWN = "showdown"


class RoundManager:
	def __init__(self):
		self.street = GameStreet.PREFLOP

	def advance(self):
		if self.street == GameStreet.PREFLOP:
			self.street = GameStreet.FLOP
		elif self.street == GameStreet.FLOP:
			self.street = GameStreet.TURN
		elif self.street == GameStreet.TURN:
			self.street = GameStreet.RIVER
		elif self.street == GameStreet.RIVER:
			self.street = GameStreet.SHOWDOWN

		return self.street

	def reset(self):
		self.street = GameStreet.PREFLOP
