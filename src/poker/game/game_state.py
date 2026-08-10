from poker.board.board import Board
from poker.cards.deck import Deck
from poker.game.betting import BettingState
from poker.game.round_manager import RoundManager
from poker.game.table import Table
from poker.game.turn_order import TurnOrder
from poker.player.player import Player


class GameState:
	def __init__(self):
		self.deck = Deck()
		self.board = Board()
		self.table = Table()
		self.players = []
		self.betting = BettingState()
		self.round_manager = RoundManager()
		self.turn_order = TurnOrder()
		self.dealer_button_index = None

	def add_player(self, player: Player):
		self.table.add_player(player)
		self.players.append(player)
		self.turn_order.players = self.players

	def player_count(self):
		return len(self.players)

	def prepare_for_hand(self):
		if len(self.table.seats) < 2:
			raise ValueError("At least two players are required")
		self._sync_hand_players()
		if len(self.players) < 2:
			raise ValueError("Not enough active players with chips for another hand")
		return self.players

	def advance_dealer_button(self):
		self._adopt_legacy_button_position()
		seat_index = self.table.advance_button()
		self._sync_hand_players()
		button_player = self.table.seats[seat_index].player
		self.dealer_button_index = self.players.index(button_player)
		return self.dealer_button_index

	def sit_out(self, player):
		self.table.sit_out(player)

	def sit_in(self, player):
		self.table.sit_in(player)

	def reset(self):
		self.deck.reset()
		self.board = Board()
		self.table = Table()
		self.players.clear()
		self.betting = BettingState()
		self.round_manager.reset()
		self.turn_order.reset()
		self.dealer_button_index = None

	def _sync_hand_players(self):
		players = self.table.hand_players()
		self.players[:] = players
		self.turn_order.players = self.players

	def _adopt_legacy_button_position(self):
		if self.table.dealer_button_seat_index is not None:
			return
		if self.dealer_button_index is None or not self.players:
			return
		if self.dealer_button_index >= len(self.players):
			return
		self.table.set_button_player(self.players[self.dealer_button_index])
