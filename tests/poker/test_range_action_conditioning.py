import random

from poker.agents.expert import full_deck
from poker.api.hand_state import HandStateView, PublicActionView, PublicPlayerView
from poker.strategy.ranges import PositionRangeModel


def _player():
	return PublicPlayerView(
		name="villain",
		chips=100,
		current_bet=0,
		total_contribution=0,
		folded=False,
		position="CO",
	)


def _state(actions=()):
	return HandStateView(
		street="preflop",
		acting_player="hero",
		hole_cards=("A♠", "K♠"),
		board=(),
		pot=10,
		target_bet=4,
		minimum_raise=2,
		dealer="hero",
		small_blind="hero",
		big_blind="villain",
		players=(_player(),),
		action_history=actions,
	)


def _average_rank(state, samples=1500):
	model = PositionRangeModel()
	rng = random.Random(123)
	deck = full_deck()
	total = 0.0

	for _ in range(samples):
		cards = model.sample_hole_cards(deck, _player(), state, rng)
		total += sum(card.rank.value for card in cards) / 2

	return total / samples


def test_observed_raise_tightens_opponent_range():
	raise_action = PublicActionView(
		street="preflop",
		player="villain",
		action="raise",
		contributed=6,
		bet_before=2,
		bet_after=8,
		pot=11,
		target=8,
	)

	passive = _average_rank(_state())
	aggressive = _average_rank(_state((raise_action,)))

	assert aggressive > passive


def test_other_players_actions_do_not_change_villain_range():
	action = PublicActionView(
		street="preflop",
		player="someone_else",
		action="all_in",
		contributed=100,
		bet_before=0,
		bet_after=100,
		pot=110,
		target=100,
	)

	assert _average_rank(_state()) == _average_rank(_state((action,)))
