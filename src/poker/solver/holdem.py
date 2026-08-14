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
	history: tuple[str, ...] = ()


class RestrictedHeadsUpHoldemGame:
	ROOT_ACTIONS = ("fold", "all_in")
	RESPONSE_ACTIONS = ("fold", "call")

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
		if state.history == ():
			return 0
		if state.history == ("all_in",):
			return 1
		raise ValueError(
			"Terminal Hold'em node has no acting player"
		)

	def is_terminal_node(self, state):
		return state.history in {
			("fold",),
			("all_in", "fold"),
			("all_in", "call"),
		}

	def terminal_node_utility(self, state, player):
		if not self.is_terminal_node(state):
			raise ValueError("Hold'em node is not terminal")

		if state.history == ("fold",):
			utility = -float(self.small_blind)
		elif state.history == ("all_in", "fold"):
			utility = float(self.big_blind)
		else:
			first = evaluate_seven_cards(
				state.deal.hole_cards[0] + state.deal.board
			)
			second = evaluate_seven_cards(
				state.deal.hole_cards[1] + state.deal.board
			)
			comparison = compare_hands(first, second)
			utility = float(
				comparison * self.starting_stack
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
			state.deal.board,
			state.history,
		)

	def legal_actions(self, state):
		if state.history == ():
			return self.ROOT_ACTIONS
		if state.history == ("all_in",):
			return self.RESPONSE_ACTIONS
		return ()

	def next_node(self, state, action):
		if action not in self.legal_actions(state):
			raise ValueError(
				f"Illegal restricted Hold'em action: {action}"
			)
		return HeadsUpHoldemNode(
			deal=state.deal,
			history=state.history + (action,),
		)

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
