import random
import secrets


class Dealer:
	def __init__(self, seed=None):
		self.base_seed = seed if seed is not None else secrets.randbits(32)
		self.hand_index = 0
		self.current_seed = None

	def start_hand(self, game_state):
		self.current_seed = self.base_seed + self.hand_index
		self.hand_index += 1
		rng = random.Random(self.current_seed)
		rng.shuffle(game_state.deck.cards)

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
