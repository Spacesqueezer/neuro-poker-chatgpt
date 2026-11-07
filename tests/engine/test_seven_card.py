from poker.cards.card import Card
from poker.enums import Rank, Suit
from poker.evaluation.seven_card import evaluate_seven_cards
from poker.evaluation.hand_rank import HandRank


def test_seven_cards_choose_best_five():
	result = evaluate_seven_cards([
		Card(Rank.ACE, Suit.SPADES),
		Card(Rank.ACE, Suit.HEARTS),
		Card(Rank.KING, Suit.CLUBS),
		Card(Rank.QUEEN, Suit.DIAMONDS),
		Card(Rank.JACK, Suit.SPADES),
		Card(Rank.TEN, Suit.HEARTS),
		Card(Rank.NINE, Suit.CLUBS),
	])

	assert result.rank == HandRank.STRAIGHT
