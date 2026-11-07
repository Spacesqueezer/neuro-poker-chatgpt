from poker.cards.card import Card
from poker.enums import Rank, Suit
from poker.evaluation.hand_value import build_tiebreaker
from poker.evaluation.hand_rank import HandRank


def test_full_house_uses_trips_before_pair():
	value = build_tiebreaker(
		[
			Card(Rank.ACE, Suit.SPADES),
			Card(Rank.ACE, Suit.HEARTS),
			Card(Rank.ACE, Suit.CLUBS),
			Card(Rank.KING, Suit.DIAMONDS),
			Card(Rank.KING, Suit.SPADES),
		],
		HandRank.FULL_HOUSE,
	)

	assert value == (14, 13)
