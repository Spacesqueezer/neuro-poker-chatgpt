class Dealer:
	def start_hand(self, game_state):
		game_state.deck.shuffle()

		for player in game_state.players:
			player.reset_for_hand()

		for _ in range(2):
			for player in game_state.players:
				player.hand.add_card(game_state.deck.draw())

	def deal_flop(self, game_state):
		game_state.deck.draw()

		for _ in range(3):
			game_state.board.add_card(game_state.deck.draw())

	def deal_turn(self, game_state):
		game_state.deck.draw()
		game_state.board.add_card(game_state.deck.draw())

	def deal_river(self, game_state):
		game_state.deck.draw()
		game_state.board.add_card(game_state.deck.draw())
