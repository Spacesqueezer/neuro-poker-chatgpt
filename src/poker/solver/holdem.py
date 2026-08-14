from dataclasses import dataclass
from math import fsum

from poker.cards.card import Card
from poker.evaluation.comparator import compare_hands
from poker.evaluation.seven_card import evaluate_seven_cards
from poker.solver.game import InitialNode


@dataclass(frozen=True)
class HeadsUpHoldemDeal:
	hole_cards: tuple[
		tuple[Card, Card],
		tuple[Card, Card],
	]
	board: tuple[Card, Card, Card, Card, Card]
	weight: float = 1.0


@dataclass(frozen=True)
class HeadsUpHoldemNode:
	deal: HeadsUpHoldemDeal
	street: str = "preflop"
	history: tuple[str, ...] = ()
	street_history: tuple[str, ...] = ()
	matched_stake: int = 0

	@property
	def public_board(self):
		if self.street == "preflop":
			return ()
		if self.street == "flop":
			return self.deal.board[:3]
		if self.street == "turn":
			return self.deal.board[:4]
		if self.street == "river":
			return self.deal.board
		raise ValueError(
			f"Unsupported Hold'em solver street: {self.street}"
		)


class RestrictedHeadsUpHoldemGame:
	ROOT_ACTIONS = ("fold", "call", "raise", "all_in")
	RAISE_RESPONSE_ACTIONS = ("fold", "call", "all_in")
	ALL_IN_RESPONSE_ACTIONS = ("fold", "call")

	def __init__(
		self,
		deals,
		starting_stack=20,
		small_blind=1,
		big_blind=2,
	):
		self.deals = tuple(deals)
		self.starting_stack = starting_stack
		self.small_blind = small_blind
		self.big_blind = big_blind
		self._validate()

	def initial_nodes(self):
		total_weight = fsum(
			deal.weight
			for deal in self.deals
		)
		return tuple(
			InitialNode(
				state=HeadsUpHoldemNode(deal),
				probability=deal.weight / total_weight,
			)
			for deal in self.deals
		)

	def player_to_act(self, state):
		if state.street == "preflop":
			if state.street_history == ():
				return 0
			if state.street_history in {
				("raise",),
				("all_in",),
			}:
				return 1
		elif state.street_history == ():
			return 1
		elif state.street_history == ("check",):
			return 0
		elif state.street_history in {
			("bet",),
			("check", "bet"),
		}:
			return (
				0
				if state.street_history == ("bet",)
				else 1
			)
		raise ValueError(
			"Terminal Hold'em node has no acting player"
		)

	def is_terminal_node(self, state):
		if state.street == "preflop":
			return state.street_history in {
				("fold",),
				("raise", "fold"),
				("raise", "all_in"),
				("all_in", "fold"),
				("all_in", "call"),
			}
		return state.street_history in {
			("bet", "fold"),
			("check", "bet", "fold"),
		} or (
			state.street == "river"
			and state.street_history in {
				("check", "check"),
				("bet", "call"),
				("check", "bet", "call"),
			}
		)

	def terminal_node_utility(self, state, player):
		if not self.is_terminal_node(state):
			raise ValueError("Hold'em node is not terminal")

		if state.history == ("fold",):
			utility = -float(self.small_blind)
		elif state.history == ("raise", "fold"):
			utility = float(self.big_blind)
		elif state.history == ("all_in", "fold"):
			utility = float(self.big_blind)
		elif state.street_history in {
			("bet", "fold"),
			("check", "bet", "fold"),
		}:
			bettor = (
				1
				if state.street_history == ("bet", "fold")
				else 0
			)
			utility = float(
				state.matched_stake
				if bettor == 0
				else -state.matched_stake
			)
		else:
			first = evaluate_seven_cards(
				state.deal.hole_cards[0] + state.deal.board
			)
			second = evaluate_seven_cards(
				state.deal.hole_cards[1] + state.deal.board
			)
			comparison = compare_hands(first, second)
			showdown_stake = (
				state.matched_stake
				if state.matched_stake
				else self.starting_stack
			)
			utility = float(
				comparison * showdown_stake
			)

		return utility if player == 0 else -utility

	def information_set_for_node(self, state, player):
		hole_cards = tuple(
			sorted(
				state.deal.hole_cards[player],
				key=lambda card: (
					card.rank.value,
					card.suit.value,
				),
			)
		)
		return (
			player,
			hole_cards,
			state.street,
			state.public_board,
			state.history,
		)

	def legal_actions(self, state):
		if state.street == "preflop":
			if state.street_history == ():
				return self.ROOT_ACTIONS
			if state.street_history == ("raise",):
				return self.RAISE_RESPONSE_ACTIONS
			if state.street_history == ("all_in",):
				return self.ALL_IN_RESPONSE_ACTIONS
			return ()
		if state.street_history == ():
			return ("check", "bet")
		if state.street_history == ("check",):
			return ("check", "bet")
		if state.street_history in {
			("bet",),
			("check", "bet"),
		}:
			return ("fold", "call")
		return ()

	def next_node(self, state, action):
		if action not in self.legal_actions(state):
			raise ValueError(
				f"Illegal restricted Hold'em action: {action}"
			)

		history = state.history + (action,)
		street_history = state.street_history + (action,)

		if state.street == "preflop":
			if street_history in {
				("call",),
				("raise", "call"),
			}:
				matched_stake = (
					self.big_blind
					if street_history == ("call",)
					else min(
						self.starting_stack,
						self.big_blind * 3,
					)
				)
				return HeadsUpHoldemNode(
					deal=state.deal,
					street="flop",
					history=history,
					matched_stake=matched_stake,
				)
			return HeadsUpHoldemNode(
				deal=state.deal,
				street=state.street,
				history=history,
				street_history=street_history,
			)

		matched_stake = state.matched_stake
		if action == "call":
			matched_stake = min(
				self.starting_stack,
				matched_stake + self.big_blind,
			)

		street_closed = street_history in {
			("check", "check"),
			("bet", "call"),
			("check", "bet", "call"),
		}
		if street_closed:
			if state.street == "river":
				return HeadsUpHoldemNode(
					deal=state.deal,
					street=state.street,
					history=history,
					street_history=street_history,
					matched_stake=matched_stake,
				)
			return HeadsUpHoldemNode(
				deal=state.deal,
				street=self._next_street(state.street),
				history=history,
				matched_stake=matched_stake,
			)

		return HeadsUpHoldemNode(
			deal=state.deal,
			street=state.street,
			history=history,
			street_history=street_history,
			matched_stake=matched_stake,
		)

	def _next_street(self, street):
		return {
			"flop": "turn",
			"turn": "river",
		}[street]

	def _validate(self):
		if not self.deals:
			raise ValueError(
				"at least one Hold'em deal is required"
			)
		if self.small_blind <= 0 or self.big_blind <= self.small_blind:
			raise ValueError(
				"blinds must satisfy 0 < small_blind < big_blind"
			)
		if self.starting_stack < self.big_blind:
			raise ValueError(
				"starting_stack must cover the big blind"
			)

		for deal in self.deals:
			if deal.weight <= 0:
				raise ValueError(
					"deal weights must be positive"
				)
			cards = (
				deal.hole_cards[0]
				+ deal.hole_cards[1]
				+ deal.board
			)
			if len(set(cards)) != 9:
				raise ValueError(
					"Hold'em deal contains duplicate cards"
				)
