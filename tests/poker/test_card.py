from poker.cards.card import Card
from poker.enums import Rank, Suit


def test_card_string():
	assert str(Card(Rank.ACE, Suit.SPADES)) == "A♠"
