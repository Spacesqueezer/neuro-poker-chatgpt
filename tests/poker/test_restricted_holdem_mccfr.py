from poker.cards.card import Card
from poker.enums import Rank, Suit
from poker.solver import (
	ExternalSamplingMCCFR,
	HeadsUpHoldemDeal,
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
