from poker.game.round_manager import GameStreet


class HandController:
	def __init__(self, dealer):
		self.dealer = dealer

	def start_hand(self, game_state):
		self.dealer.start_hand(game_state)

	def advance_street(self, game_state):
		street = game_state.round_manager.advance()

		if street == GameStreet.FLOP:
			self.dealer.deal_flop(game_state)
		elif street == GameStreet.TURN:
			self.dealer.deal_turn(game_state)
		elif street == GameStreet.RIVER:
			self.dealer.deal_river(game_state)

		return street
