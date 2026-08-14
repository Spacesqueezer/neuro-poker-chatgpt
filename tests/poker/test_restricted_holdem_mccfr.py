from poker.cards.card import Card
from poker.enums import Rank, Suit
from poker.solver import (
	ExternalSamplingMCCFR,
	HeadsUpHoldemDeal,
	HoldemActionAbstraction,
	RestrictedHeadsUpHoldemGame,
)


def test_mccfr_runs_with_restricted_holdem_game():
	deal = HeadsUpHoldemDeal(
		hole_cards=(
			(
				Card(Rank.ACE, Suit.SPADES),
				Card(Rank.ACE, Suit.HEARTS),
			),
			(
				Card(Rank.KING, Suit.SPADES),
				Card(Rank.KING, Suit.HEARTS),
			),
		),
		board=(
			Card(Rank.TWO, Suit.CLUBS),
			Card(Rank.THREE, Suit.DIAMONDS),
			Card(Rank.FOUR, Suit.HEARTS),
			Card(Rank.FIVE, Suit.CLUBS),
			Card(Rank.SEVEN, Suit.SPADES),
		),
	)
	game = RestrictedHeadsUpHoldemGame((deal,))

	result = ExternalSamplingMCCFR(
		game,
		seed=42,
	).train(10)

	assert result.iterations == 10
	assert result.average_strategy
	assert result.cumulative_regret

	player_one_regrets = [
		regrets
		for info_set, regrets
		in result.cumulative_regret.items()
		if info_set[0] == 1
	]
	assert player_one_regrets
	assert any(
		any(abs(value) > 0.0 for value in regrets.values())
		for regrets in player_one_regrets
	)


def test_mccfr_is_deterministic_on_expanded_restricted_holdem_tree():
	deal = HeadsUpHoldemDeal(
		hole_cards=(
			(
				Card(Rank.ACE, Suit.SPADES),
				Card(Rank.ACE, Suit.HEARTS),
			),
			(
				Card(Rank.KING, Suit.SPADES),
				Card(Rank.KING, Suit.HEARTS),
			),
		),
		board=(
			Card(Rank.TWO, Suit.CLUBS),
			Card(Rank.THREE, Suit.DIAMONDS),
			Card(Rank.FOUR, Suit.HEARTS),
			Card(Rank.FIVE, Suit.CLUBS),
			Card(Rank.SEVEN, Suit.SPADES),
		),
	)
	game = RestrictedHeadsUpHoldemGame(
		(deal,),
		action_abstraction=HoldemActionAbstraction(
			postflop_bet_sizes_bb=(1, 2),
			postflop_raise_increment_multiplier=2,
		),
	)

	first = ExternalSamplingMCCFR(
		game,
		seed=73,
	).train(20)
	second = ExternalSamplingMCCFR(
		game,
		seed=73,
	).train(20)

	assert first.average_strategy == second.average_strategy
	assert first.cumulative_regret == second.cumulative_regret
	assert any(
		"raise" in strategy
		for strategy in first.average_strategy.values()
	)
	for strategy in first.average_strategy.values():
		assert abs(sum(strategy.values()) - 1.0) < 1e-12
