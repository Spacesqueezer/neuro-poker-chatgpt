from poker.evaluation.seven_card import evaluate_seven_cards
from poker.game.action_resolver import ActionResolver
from poker.game.actions import PlayerAction
from poker.game.betting_round import BettingRound
from poker.game.hand_history import HandHistory, create_hand_id
from poker.game.positions import positions_by_player
from poker.game.pot_manager import PotManager
from poker.game.round_manager import GameStreet


class HandController:
	def __init__(self, dealer, action_resolver=None, small_blind=1, big_blind=2):
		if small_blind <= 0:
			raise ValueError("Small blind must be positive")
		if big_blind <= small_blind:
			raise ValueError("Big blind must exceed small blind")

		self.dealer = dealer
		self.pot_manager = PotManager()
		self.action_resolver = action_resolver or ActionResolver()
		self.small_blind = small_blind
		self.big_blind = big_blind
		self.minimum_raise = big_blind
		self.betting_round = None
		self.small_blind_index = None
		self.big_blind_index = None
		self.showdown_results = {}
		self.showdown_winners = []
		self.showdown_payouts = {}
		self.showdown_refunds = {}
		self.showdown_pots = []
		self.hand_history = None

	def start_hand(self, game_state):
		game_state.prepare_for_hand()

		game_state.deck.reset()
		game_state.board.cards.clear()
		game_state.betting.pot = 0
		game_state.betting.current_bet = 0
		game_state.round_manager.reset()
		game_state.turn_order.reset()
		self.minimum_raise = self.big_blind
		self.showdown_results = {}
		self.showdown_winners = []
		self.showdown_payouts = {}
		self.showdown_refunds = {}
		self.showdown_pots = []

		game_state.advance_dealer_button()
		self.dealer.start_hand(game_state)
		self._assign_blinds(game_state)
		self._post_blinds(game_state)
		self._start_history(game_state)
		self.betting_round = BettingRound(game_state.players)
		self._set_preflop_first_player(game_state)

		if self._betting_is_closed_by_all_in(self.betting_round.active_players()):
			self._finish_betting_round(game_state)

	def current_player(self, game_state):
		return game_state.turn_order.current_player()

	def process_action(self, game_state, action, amount=0):
		if self.betting_round is None:
			raise RuntimeError("Hand has not been started")

		player = self.current_player(game_state)

		if player is None:
			raise RuntimeError("No player available to act")
		if player.chips <= 0:
			raise ValueError("All-in player cannot act")

		previous_bet = game_state.betting.current_bet
		full_raise = False
		short_raise = False
		chips_before = player.chips
		bet_before = player.current_bet

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
			contribution = min(call_amount, player.chips)
			self.action_resolver.apply(player, action, contribution)
		elif action == PlayerAction.BET:
			if previous_bet != 0:
				raise ValueError("Cannot bet while facing an existing bet")
			if amount < self.big_blind:
				raise ValueError(f"Minimum bet is {self.big_blind}")
			self.action_resolver.apply(player, action, amount)
			game_state.betting.current_bet = player.current_bet
			self.minimum_raise = amount
			full_raise = True
		elif action == PlayerAction.RAISE:
			if previous_bet == 0:
				raise ValueError("Cannot raise without an existing bet")
			if not self.betting_round.can_raise(
				player,
				current_target=previous_bet,
				minimum_raise=self.minimum_raise,
			):
				raise ValueError("Betting was not reopened by the short all-in")
			if amount <= previous_bet:
				raise ValueError("Raise target must exceed the current bet")

			raise_size = amount - previous_bet
			minimum_target = previous_bet + self.minimum_raise
			if raise_size < self.minimum_raise:
				raise ValueError(f"Minimum raise target is {minimum_target}")

			contribution = amount - player.current_bet
			self.action_resolver.apply(player, action, contribution)
			game_state.betting.current_bet = player.current_bet
			self.minimum_raise = raise_size
			full_raise = True
		elif action == PlayerAction.ALL_IN:
			all_in_amount = player.chips
			if all_in_amount <= 0:
				raise ValueError("Player has no chips")

			all_in_target = player.current_bet + all_in_amount

			self.action_resolver.apply(player, action, all_in_amount)

			if all_in_target > previous_bet:
				increase = all_in_target - previous_bet
				game_state.betting.current_bet = all_in_target

				if previous_bet == 0:
					if all_in_target >= self.big_blind:
						self.minimum_raise = all_in_target
						full_raise = True
					else:
						short_raise = True
				elif increase >= self.minimum_raise:
					self.minimum_raise = increase
					full_raise = True
				else:
					short_raise = True
		else:
			raise ValueError("Unsupported action")

		self._record_action(
			game_state,
			player,
			action,
			amount,
			chips_before,
			bet_before,
		)

		bet_increased = game_state.betting.current_bet > previous_bet
		self.betting_round.mark_action(
			player,
			bet_increased=bet_increased,
			full_raise=full_raise,
			short_raise=short_raise,
			target_bet=game_state.betting.current_bet,
		)

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

		if street in {GameStreet.FLOP, GameStreet.TURN, GameStreet.RIVER}:
			self._record_street(game_state, street)

		return street

	def position_name(self, game_state, player_index):
		if player_index == game_state.dealer_button_index:
			return "BTN"
		if player_index == self.small_blind_index:
			return "SB"
		if player_index == self.big_blind_index:
			return "BB"
		return ""

	def total_pot(self, game_state):
		return game_state.betting.pot + sum(player.current_bet for player in game_state.players)

	def _assign_blinds(self, game_state):
		player_count = len(game_state.players)
		dealer_index = game_state.dealer_button_index

		if player_count == 2:
			self.small_blind_index = dealer_index
			self.big_blind_index = (dealer_index + 1) % player_count
			return

		self.small_blind_index = (dealer_index + 1) % player_count
		self.big_blind_index = (dealer_index + 2) % player_count

	def _post_blinds(self, game_state):
		small_blind_player = game_state.players[self.small_blind_index]
		big_blind_player = game_state.players[self.big_blind_index]

		small_blind_amount = min(self.small_blind, small_blind_player.chips)
		big_blind_amount = min(self.big_blind, big_blind_player.chips)

		if small_blind_amount > 0:
			small_blind_player.bet(small_blind_amount)
		if big_blind_amount > 0:
			big_blind_player.bet(big_blind_amount)

		game_state.betting.current_bet = self.big_blind

	def _set_preflop_first_player(self, game_state):
		if len(game_state.players) == 2:
			game_state.turn_order.set_position(game_state.dealer_button_index)
			return

		game_state.turn_order.set_to_next_active_after(self.big_blind_index)

	def _set_postflop_first_player(self, game_state):
		game_state.turn_order.set_to_next_active_after(game_state.dealer_button_index)


	def _finish_betting_round(self, game_state):
		for player in game_state.players:
			game_state.betting.collect_player_bet(player)

		game_state.betting.current_bet = 0

		active_players = self.betting_round.active_players()
		if len(active_players) == 1:
			winner = active_players[0]
			payout = game_state.betting.pot
			winner.chips += payout
			game_state.betting.pot = 0
			game_state.round_manager.street = GameStreet.COMPLETE
			game_state.table.sync_statuses()
			if self.hand_history is not None:
				self.hand_history.add_event("uncontested", winner=winner.name, payout=payout)
				self.hand_history.finish("complete", game_state.players)
			return GameStreet.COMPLETE

		if self._betting_is_closed_by_all_in(active_players):
			return self._run_out_to_showdown(game_state)

		street = self.advance_street(game_state)

		if street == GameStreet.SHOWDOWN:
			self._resolve_showdown(game_state)
		else:
			self.minimum_raise = self.big_blind
			self.betting_round = BettingRound(game_state.players)
			self._set_postflop_first_player(game_state)

		return street

	def _betting_is_closed_by_all_in(self, active_players):
		return sum(player.chips > 0 for player in active_players) <= 1

	def _run_out_to_showdown(self, game_state):
		while game_state.round_manager.street not in {GameStreet.SHOWDOWN, GameStreet.COMPLETE}:
			self.advance_street(game_state)

		if game_state.round_manager.street == GameStreet.SHOWDOWN:
			self._resolve_showdown(game_state)

		return game_state.round_manager.street

	def _resolve_showdown(self, game_state):
		if len(game_state.board.cards) != 5:
			raise RuntimeError("Showdown requires five community cards")

		contenders = [player for player in game_state.players if not player.folded]
		if len(contenders) < 2:
			raise RuntimeError("Showdown requires at least two active players")

		self.showdown_results = {
			player: evaluate_seven_cards([*player.hand.cards, *game_state.board.cards])
			for player in contenders
		}
		settlement = self.pot_manager.settle(
			game_state.players,
			game_state.dealer_button_index,
			self.showdown_results,
			fallback_pot=game_state.betting.pot,
		)
		self.showdown_payouts = settlement.payouts
		self.showdown_refunds = settlement.refunds
		self.showdown_winners = list(settlement.winners)
		self.showdown_pots = [
			(layer.kind, layer.amount, list(layer.eligible_players), list(layer.winners))
			for layer in settlement.layers
		]
		game_state.betting.pot = 0
		game_state.table.sync_statuses()
		if self.hand_history is not None:
			self.hand_history.add_event(
				"showdown",
				board=[str(card) for card in game_state.board.cards],
				results={
					player.name: {
						"rank": result.rank.name.lower(),
						"cards": [str(card) for card in result.cards],
						"payout": settlement.payouts.get(player, 0),
						"refund": settlement.refunds.get(player, 0),
					}
					for player, result in self.showdown_results.items()
				},
				pots=[
					{
						"kind": layer.kind,
						"amount": layer.amount,
						"eligible": [player.name for player in layer.eligible_players],
						"winners": [player.name for player in layer.winners],
					}
					for layer in settlement.layers
				],
			)
			self.hand_history.finish("showdown", game_state.players)

	def _start_history(self, game_state):
		dealer = game_state.players[game_state.dealer_button_index]
		player_positions = positions_by_player(
			game_state.players,
			game_state.dealer_button_index,
		)
		self.hand_history = HandHistory(
			hand_id=create_hand_id(),
			players=[
				{
					"name": player.name,
					"starting_chips": player.chips + player.current_bet,
					"cards": [str(card) for card in player.hand.cards],
					"position": player_positions[player.name],
				}
				for player in game_state.players
			],
			dealer=dealer.name,
			small_blind=self.small_blind,
			big_blind=self.big_blind,
			seed=getattr(self.dealer, "current_seed", None),
		)
		small_blind_player = game_state.players[self.small_blind_index]
		big_blind_player = game_state.players[self.big_blind_index]
		self.hand_history.add_event(
			"blinds",
			small_blind_player=small_blind_player.name,
			big_blind_player=big_blind_player.name,
			small_blind=small_blind_player.current_bet,
			big_blind=big_blind_player.current_bet,
			pot=self.total_pot(game_state),
			target=game_state.betting.current_bet,
		)

	def _record_action(self, game_state, player, action, amount, chips_before, bet_before):
		if self.hand_history is None:
			return
		self.hand_history.add_event(
			"action",
			street=game_state.round_manager.street.value,
			player=player.name,
			action=action.value,
			requested_amount=amount,
			contributed=(chips_before - player.chips),
			bet_before=bet_before,
			bet_after=player.current_bet,
			total_contribution=player.total_contribution,
			chips_before=chips_before,
			chips_after=player.chips,
			pot=self.total_pot(game_state),
			target=game_state.betting.current_bet,
		)

	def _record_street(self, game_state, street):
		if self.hand_history is None:
			return
		self.hand_history.add_event(
			"street",
			street=street.value,
			board=[str(card) for card in game_state.board.cards],
			pot=game_state.betting.pot,
			stacks={player.name: player.chips for player in game_state.players},
		)

	def _build_pot_layers(self, game_state):
		return self.pot_manager.build_layers(game_state.players)

	def _winners_left_of_dealer(self, game_state, winners):
		return self.pot_manager._order_left_of_dealer(
			game_state.players,
			game_state.dealer_button_index,
			winners,
		)
