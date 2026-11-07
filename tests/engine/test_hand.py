import pytest

from poker.cards.card import Card
from poker.enums import Rank, Suit
from poker.hand.hand import Hand


def test_hand_accepts_two_cards():
	hand = Hand()

	hand.add_card(Card(Rank.ACE, Suit.SPADES))
	hand.add_card(Card(Rank.KING, Suit.HEARTS))

	assert hand.is_complete()


def test_hand_cannot_have_three_cards():
	with pytest.raises(ValueError):
		Hand([
			Card(Rank.ACE, Suit.SPADES),
			Card(Rank.KING, Suit.HEARTS),
			Card(Rank.QUEEN, Suit.CLUBS),
		])
