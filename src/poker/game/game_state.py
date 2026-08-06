from poker.board.board import Board
from poker.cards.deck import Deck
from poker.hand.hand import Hand


class GameState:
	def __init__(self):
		self.deck = Deck()
		self.board = Board()
		self.players = []

	def add_player(self, hand=None):
		self.players.append(hand or Hand())

	def player_count(self):
		return len(self.players)

	def reset(self):
		self.deck.reset()
		self.board = Board()
		self.players.clear()
