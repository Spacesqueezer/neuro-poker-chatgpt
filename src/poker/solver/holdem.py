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
class HoldemActionAbstraction:
	preflop_raise_bb: int = 3
	postflop_bet_sizes_bb: tuple[int, ...] = (1, 2)
	postflop_raise_increment_multiplier: int = 1


@dataclass(frozen=True)
class HeadsUpHoldemNode:
	deal: HeadsUpHoldemDeal
	street: str = "preflop"
	history: tuple[str, ...] = ()
	street_history: tuple[str, ...] = ()
	commitments: tuple[int, int] = (0, 0)
	starting_stacks: tuple[int, int] = (20, 20)

	@property
	def matched_stake(self):
		return min(self.commitments)

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
		starting_stacks=None,
		small_blind=1,
		big_blind=2,
		action_abstraction=None,
	):
		self.deals = tuple(deals)
		self.starting_stack = starting_stack
		self.starting_stacks = (
			tuple(starting_stacks)
			if starting_stacks is not None
			else (starting_stack, starting_stack)
		)
		self.small_blind = small_blind
		self.big_blind = big_blind
		self.action_abstraction = (
			action_abstraction
			or HoldemActionAbstraction()
		)
		self._validate()

	def initial_nodes(self):
		total_weight = fsum(
			deal.weight
			for deal in self.deals
		)
		return tuple(
			InitialNode(
				state=HeadsUpHoldemNode(
					deal,
					commitments=(
						self.small_blind,
						self.big_blind,
					),
					starting_stacks=self.starting_stacks,
				),
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
		elif (
			len(state.street_history) == 1
			and self._is_postflop_bet_action(
				state.street_history[0]
			)
		):
			return 0
		elif (
			len(state.street_history) == 2
			and state.street_history[0] == "check"
			and self._is_postflop_bet_action(
				state.street_history[1]
			)
		):
			return 1
		elif self._is_postflop_raise(
			state.street_history
		):
			return (
				0
				if state.street_history[0] == "check"
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
		return self._is_postflop_fold(
			state.street_history
		) or (
			state.street == "river"
			and (
				state.street_history == ("check", "check")
				or self._is_postflop_bet_call(
					state.street_history
				)
			)
		)

	def terminal_node_utility(self, state, player):
		if not self.is_terminal_node(state):
			raise ValueError("Hold'em node is not terminal")

		folded_player = self._folded_player(state)
		if folded_player is not None:
			utility = float(
				-state.commitments[0]
				if folded_player == 0
				else state.commitments[1]
			)
		else:
			first = evaluate_seven_cards(
				state.deal.hole_cards[0] + state.deal.board
			)
			second = evaluate_seven_cards(
				state.deal.hole_cards[1] + state.deal.board
			)
			comparison = compare_hands(first, second)
			utility = float(
				comparison * state.matched_stake
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
			state.commitments,
			state.starting_stacks,
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
		if state.street_history in {
			(),
			("check",),
		}:
			return (
				"check",
				*self._postflop_bet_actions(),
			)
		if self._is_postflop_open_bet(
			state.street_history
		):
			return ("fold", "call", "raise")
		if self._is_postflop_raise(
			state.street_history
		):
			return ("fold", "call")
		return ()

	def next_node(self, state, action):
		if action not in self.legal_actions(state):
			raise ValueError(
				f"Illegal restricted Hold'em action: {action}"
			)

		actor = self.player_to_act(state)
		history = state.history + (action,)
		street_history = state.street_history + (action,)
		commitments = list(state.commitments)

		if state.street == "preflop":
			if action == "call":
				commitments[actor] = min(
					self._stack_for(actor),
					max(commitments),
				)
			elif action == "raise":
				commitments[actor] = min(
					self._stack_for(actor),
					self.big_blind
					* self.action_abstraction.preflop_raise_bb,
				)
			elif action == "all_in":
				commitments[actor] = self._stack_for(actor)
				if state.street_history == ("raise",):
					opponent = 1 - actor
					commitments[opponent] = max(
						commitments[opponent],
						min(
							self._stack_for(opponent),
							commitments[actor],
						),
					)

			if street_history in {
				("call",),
				("raise", "call"),
			}:
				return HeadsUpHoldemNode(
					deal=state.deal,
					street="flop",
					history=history,
					commitments=tuple(commitments),
					starting_stacks=state.starting_stacks,
				)
			return HeadsUpHoldemNode(
				deal=state.deal,
				street=state.street,
				history=history,
				street_history=street_history,
				commitments=tuple(commitments),
				starting_stacks=state.starting_stacks,
			)

		if self._is_postflop_bet_action(action):
			commitments[actor] = min(
				self._stack_for(actor),
				commitments[actor]
				+ (
					self.big_blind
					* self._postflop_bet_size_bb(action)
				),
			)
		elif action == "raise":
			outstanding = max(commitments)
			raise_increment = (
				outstanding - commitments[actor]
			)
			commitments[actor] = min(
				self._stack_for(actor),
				outstanding
				+ (
					raise_increment
					* self.action_abstraction
					.postflop_raise_increment_multiplier
				),
			)
		elif action == "call":
			commitments[actor] = min(
				self._stack_for(actor),
				max(commitments),
			)

		street_closed = (
			street_history == ("check", "check")
			or self._is_postflop_bet_call(
				street_history
			)
		)
		if street_closed:
			if state.street == "river":
				return HeadsUpHoldemNode(
					deal=state.deal,
					street=state.street,
					history=history,
					street_history=street_history,
					commitments=tuple(commitments),
					starting_stacks=state.starting_stacks,
				)
			return HeadsUpHoldemNode(
				deal=state.deal,
				street=self._next_street(state.street),
				history=history,
				commitments=tuple(commitments),
				starting_stacks=state.starting_stacks,
			)

		return HeadsUpHoldemNode(
			deal=state.deal,
			street=state.street,
			history=history,
			street_history=street_history,
			commitments=tuple(commitments),
			starting_stacks=state.starting_stacks,
		)

	def _folded_player(self, state):
		if state.street == "preflop":
			if state.history == ("fold",):
				return 0
			if state.history in {
				("raise", "fold"),
				("all_in", "fold"),
			}:
				return 1

		if self._is_postflop_fold(
			state.street_history
		):
			prefix = state.street_history[:-1]
			if self._is_postflop_raise(prefix):
				return (
					0
					if prefix[0] == "check"
					else 1
				)
			return (
				1
				if prefix[0] == "check"
				else 0
			)

		return None

	def _postflop_bet_actions(self):
		return tuple(
			f"bet_{size}bb"
			for size
			in self.action_abstraction.postflop_bet_sizes_bb
		)

	def _is_postflop_bet_action(self, action):
		return action in self._postflop_bet_actions()

	def _postflop_bet_size_bb(self, action):
		for size in (
			self.action_abstraction.postflop_bet_sizes_bb
		):
			if action == f"bet_{size}bb":
				return size
		raise ValueError(
			f"Unknown postflop bet action: {action}"
		)

	def _is_postflop_open_bet(self, street_history):
		return (
			len(street_history) == 1
			and self._is_postflop_bet_action(
				street_history[0]
			)
		) or (
			len(street_history) == 2
			and street_history[0] == "check"
			and self._is_postflop_bet_action(
				street_history[1]
			)
		)

	def _is_postflop_raise(self, street_history):
		return (
			street_history[-1:] == ("raise",)
			and self._is_postflop_open_bet(
				street_history[:-1]
			)
		)

	def _is_postflop_fold(self, street_history):
		return (
			street_history[-1:] == ("fold",)
			and (
				self._is_postflop_open_bet(
					street_history[:-1]
				)
				or self._is_postflop_raise(
					street_history[:-1]
				)
			)
		)

	def _is_postflop_bet_call(self, street_history):
		return (
			street_history[-1:] == ("call",)
			and (
				self._is_postflop_open_bet(
					street_history[:-1]
				)
				or self._is_postflop_raise(
					street_history[:-1]
				)
			)
		)

	def _next_street(self, street):
		return {
			"flop": "turn",
			"turn": "river",
		}[street]

	def _stack_for(self, player):
		return self.starting_stacks[player]

	def _validate(self):
		if not self.deals:
			raise ValueError(
				"at least one Hold'em deal is required"
			)
		if self.small_blind <= 0 or self.big_blind <= self.small_blind:
			raise ValueError(
				"blinds must satisfy 0 < small_blind < big_blind"
			)
		if len(self.starting_stacks) != 2:
			raise ValueError(
				"starting_stacks must contain exactly two stacks"
			)
		if self.starting_stacks[0] < self.small_blind:
			raise ValueError(
				"player 0 starting stack must cover the small blind"
			)
		if self.starting_stacks[1] < self.big_blind:
			raise ValueError(
				"player 1 starting stack must cover the big blind"
			)
		if self.action_abstraction.preflop_raise_bb < 2:
			raise ValueError(
				"preflop_raise_bb must be at least 2"
			)
		postflop_sizes = (
			self.action_abstraction.postflop_bet_sizes_bb
		)
		if not postflop_sizes:
			raise ValueError(
				"postflop_bet_sizes_bb must not be empty"
			)
		if any(size <= 0 for size in postflop_sizes):
			raise ValueError(
				"postflop_bet_sizes_bb must be positive"
			)
		if tuple(sorted(set(postflop_sizes))) != postflop_sizes:
			raise ValueError(
				"postflop_bet_sizes_bb must be unique and increasing"
			)
		if (
			self.action_abstraction
			.postflop_raise_increment_multiplier
			<= 0
		):
			raise ValueError(
				"postflop_raise_increment_multiplier must be positive"
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
