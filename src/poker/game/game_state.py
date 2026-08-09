from poker.board.board import Board
from poker.cards.deck import Deck
from poker.game.betting import BettingState
from poker.game.round_manager import RoundManager
from poker.game.turn_order import TurnOrder
from poker.player.player import Player


class GameState:
	def __init__(self):
		self.deck = Deck()
		self.board = Board()
		self.players = []
		self.betting = BettingState()
		self.round_manager = RoundManager()
		self.turn_order = TurnOrder()
		self.dealer_button_index = None

	def add_player(self, player: Player):
		self.players.append(player)
		self.turn_order.players = self.players

	def player_count(self):
		return len(self.players)

	def advance_dealer_button(self):
		if not self.players:
			raise ValueError("Cannot advance dealer button without players")

		if self.dealer_button_index is None:
			self.dealer_button_index = 0
		else:
			self.dealer_button_index = (self.dealer_button_index + 1) % len(self.players)

		return self.dealer_button_index

	def reset(self):
		self.deck.reset()
		self.board = Board()
		self.players.clear()
		self.betting = BettingState()
		self.round_manager.reset()
		self.turn_order.reset()
		self.dealer_button_index = None
