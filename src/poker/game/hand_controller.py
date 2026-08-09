from poker.game.action_resolver import ActionResolver
from poker.game.actions import PlayerAction
from poker.game.betting_round import BettingRound
from poker.game.round_manager import GameStreet


class HandController:
	def __init__(self, dealer, action_resolver=None):
		self.dealer = dealer
		self.action_resolver = action_resolver or ActionResolver()
		self.betting_round = None

	def start_hand(self, game_state):
		if len(game_state.players) < 2:
			raise ValueError("At least two players are required")

		game_state.deck.reset()
		game_state.board.cards.clear()
		game_state.betting.pot = 0
		game_state.betting.current_bet = 0
		game_state.round_manager.reset()
		game_state.turn_order.reset()

		self.dealer.start_hand(game_state)
		self.betting_round = BettingRound(game_state.players)

	def current_player(self, game_state):
		return game_state.turn_order.current_player()

	def process_action(self, game_state, action, amount=0):
		if self.betting_round is None:
			raise RuntimeError("Hand has not been started")

		player = self.current_player(game_state)

		if player is None:
			raise RuntimeError("No player available to act")

		previous_bet = game_state.betting.current_bet

		if action == PlayerAction.FOLD:
			self.action_resolver.apply(player, action)
		elif action == PlayerAction.CHECK:
			if player.current_bet != previous_bet:
				raise ValueError("Cannot check while facing a bet")
			self.action_resolver.apply(player, action)
		elif action == PlayerAction.CALL:
			call_amount = previous_bet - player.current_bet
			if call_amount <= 0:
				raise ValueError("Nothing to call")
			self.action_resolver.apply(player, action, call_amount)
		elif action == PlayerAction.BET:
			if previous_bet != 0:
				raise ValueError("Cannot bet while facing an existing bet")
			if amount <= 0:
				raise ValueError("Bet amount must be positive")
			self.action_resolver.apply(player, action, amount)
			game_state.betting.current_bet = player.current_bet
		elif action == PlayerAction.RAISE:
			if previous_bet == 0:
				raise ValueError("Cannot raise without an existing bet")
			if amount <= previous_bet:
				raise ValueError("Raise target must exceed the current bet")
			contribution = amount - player.current_bet
			self.action_resolver.apply(player, action, contribution)
			game_state.betting.current_bet = player.current_bet
		elif action == PlayerAction.ALL_IN:
			all_in_amount = player.chips
			if all_in_amount <= 0:
				raise ValueError("Player has no chips")
			if player.current_bet + all_in_amount < previous_bet:
				raise ValueError("Short all-in requires side pot support")
			self.action_resolver.apply(player, action, all_in_amount)
			game_state.betting.current_bet = max(
				game_state.betting.current_bet,
				player.current_bet,
			)
		else:
			raise ValueError("Unsupported action")

		bet_increased = game_state.betting.current_bet > previous_bet
		self.betting_round.mark_action(player, bet_increased=bet_increased)

		if self.betting_round.is_complete():
			return self._finish_betting_round(game_state)

		game_state.turn_order.next_active_player()
		return game_state.round_manager.street

	def advance_street(self, game_state):
		street = game_state.round_manager.advance()

		if street == GameStreet.FLOP:
			self.dealer.deal_flop(game_state)
		elif street == GameStreet.TURN:
			self.dealer.deal_turn(game_state)
		elif street == GameStreet.RIVER:
			self.dealer.deal_river(game_state)

		return street

	def _finish_betting_round(self, game_state):
		for player in game_state.players:
			game_state.betting.collect_player_bet(player)

		game_state.betting.current_bet = 0

		active_players = self.betting_round.active_players()
		if len(active_players) == 1:
			game_state.round_manager.street = GameStreet.SHOWDOWN
			return GameStreet.SHOWDOWN

		street = self.advance_street(game_state)

		if street != GameStreet.SHOWDOWN:
			self.betting_round = BettingRound(game_state.players)
			game_state.turn_order.reset()
			while game_state.turn_order.current_player().folded:
				game_state.turn_order.next_active_player()

		return street
