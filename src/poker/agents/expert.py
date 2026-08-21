import random

from poker.api import ActionDecision
from poker.cards.card import Card
from poker.enums import Rank, Suit
from poker.evaluation.seven_card import evaluate_seven_cards
from poker.game.actions import PlayerAction
from poker.strategy.ranges import PositionRangeModel

RANK_BY_SYMBOL = {str(rank.value): rank for rank in Rank}
RANK_BY_SYMBOL.update({
	"J": Rank.JACK,
	"Q": Rank.QUEEN,
	"K": Rank.KING,
	"A": Rank.ACE,
})
SUIT_BY_SYMBOL = {
	"♣": Suit.CLUBS,
	"♦": Suit.DIAMONDS,
	"♥": Suit.HEARTS,
	"♠": Suit.SPADES,
}


def parse_card(value):
	rank_symbol = value[:-1]
	suit_symbol = value[-1]

	try:
		return Card(
			RANK_BY_SYMBOL[rank_symbol],
			SUIT_BY_SYMBOL[suit_symbol],
		)
	except KeyError as error:
		raise ValueError(f"Unsupported card representation: {value}") from error


def full_deck():
	return [
		Card(rank, suit)
		for rank in Rank
		for suit in Suit
	]


class MonteCarloEquityEstimator:
	def __init__(
		self,
		samples=300,
		seed=None,
		range_model=None,
		profile_provider=None,
		agent_id=None,
	):
		if samples <= 0:
			raise ValueError("samples must be positive")

		self.samples = samples
		self.random = random.Random(seed)
		self.range_model = range_model or PositionRangeModel(
			profile_provider=profile_provider,
			agent_id=agent_id,
		)

	def estimate(self, state):
		hero_cards = [parse_card(value) for value in state.hole_cards]
		board = [parse_card(value) for value in state.board]
		opponents = [
			player
			for player in state.players
			if player.name != state.acting_player and not player.folded
		]

		if not opponents:
			return 1.0

		known = set(hero_cards + board)
		available = [
			card
			for card in full_deck()
			if card not in known
		]
		board_needed = 5 - len(board)
		cards_needed = board_needed + 2 * len(opponents)

		if cards_needed > len(available):
			raise ValueError("Not enough unknown cards for equity simulation")

		equity = 0.0

		for _ in range(self.samples):
			remaining = list(available)
			opponent_hands = []

			for opponent in opponents:
				opponent_cards = self.range_model.sample_hole_cards(
					remaining,
					opponent,
					state,
					self.random,
				)
				opponent_hands.append(opponent_cards)

				for card in opponent_cards:
					remaining.remove(card)

			runout = self.random.sample(
				remaining,
				board_needed,
			)
			final_board = board + runout

			hero_result = evaluate_seven_cards(hero_cards + final_board)
			results = [hero_result]

			for opponent_cards in opponent_hands:
				results.append(
					evaluate_seven_cards(
						list(opponent_cards) + final_board
					)
				)

			best = max(
				results,
				key=lambda result: (result.rank, result.tiebreaker),
			)
			winners = [
				index
				for index, result in enumerate(results)
				if (result.rank, result.tiebreaker)
				== (best.rank, best.tiebreaker)
			]

			if 0 in winners:
				equity += 1.0 / len(winners)

		return equity / self.samples


class ExpertAgent:
	def __init__(
		self,
		seed=None,
		equity_samples=300,
		raise_margin=0.18,
		value_bet_threshold=0.58,
		range_model=None,
		profile_provider=None,
		agent_id=None,
	):
		self.equity = MonteCarloEquityEstimator(
			samples=equity_samples,
			seed=seed,
			range_model=range_model,
			profile_provider=profile_provider,
			agent_id=agent_id,
		)
		self.raise_margin = raise_margin
		self.value_bet_threshold = value_bet_threshold

	def choose_action(self, state, legal):
		equity = self.equity.estimate(state)
		call_amount = legal.call_amount
		pot_after_call = state.pot + call_amount
		pot_odds = (
			call_amount / pot_after_call
			if call_amount > 0 and pot_after_call > 0
			else 0.0
		)

		if call_amount > 0:
			if equity + 0.03 < pot_odds:
				return self._simple(legal, PlayerAction.FOLD, PlayerAction.CALL)

			if (
				equity >= max(0.62, pot_odds + self.raise_margin)
				and PlayerAction.RAISE in legal.actions
			):
				return ActionDecision(
					PlayerAction.RAISE,
					self._raise_target(state, legal),
				)

			if PlayerAction.CALL in legal.actions:
				return ActionDecision(PlayerAction.CALL)

			return self._simple(legal, PlayerAction.ALL_IN, PlayerAction.FOLD)

		if (
			equity >= self.value_bet_threshold
			and PlayerAction.BET in legal.actions
		):
			return ActionDecision(
				PlayerAction.BET,
				self._bet_amount(state, legal),
			)

		if (
			equity >= 0.68
			and PlayerAction.RAISE in legal.actions
		):
			return ActionDecision(
				PlayerAction.RAISE,
				self._raise_target(state, legal),
			)

		return self._simple(
			legal,
			PlayerAction.CHECK,
			PlayerAction.ALL_IN,
			PlayerAction.FOLD,
		)

	def _bet_amount(self, state, legal):
		target = max(
			legal.min_bet,
			round(max(state.pot, legal.min_bet) * 0.65),
		)
		return min(target, legal.max_bet)

	def _raise_target(self, state, legal):
		target = max(
			legal.min_raise_to,
			state.target_bet + round(
				max(state.pot, state.minimum_raise) * 0.65
			),
		)
		return min(target, legal.max_raise_to)

	def _simple(self, legal, *actions):
		for action in actions:
			if action in legal.actions:
				return ActionDecision(action)

		raise RuntimeError("ExpertAgent has no supported legal action")
