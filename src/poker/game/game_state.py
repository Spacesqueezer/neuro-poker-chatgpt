from poker.board.board import Board
from poker.cards.deck import Deck
from poker.game.betting import BettingState
from poker.game.round_manager import RoundManager
from poker.game.turn_order import TurnOrder
from poker.hand.hand import Hand


class GameState:
	def __init__(self):
		self.deck = Deck()
		self.board = Board()
		self.players = []
		self.betting = BettingState()
		self.round_manager = RoundManager()
		self.turn_order = TurnOrder()

	def add_player(self, hand=None):
		self.players.append(hand or Hand())
		self.turn_order.players = self.players

	def player_count(self):
		return len(self.players)

	def reset(self):
		self.deck.reset()
		self.board = Board()
		self.players.clear()
		self.betting = BettingState()
		self.round_manager.reset()
		self.turn_order.reset()
