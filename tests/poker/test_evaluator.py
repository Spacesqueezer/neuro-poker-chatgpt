from poker.cards.card import Card
from poker.enums import Rank, Suit
from poker.evaluation.evaluator import evaluate
from poker.evaluation.hand_rank import HandRank


def test_evaluator_returns_result():
	result = evaluate([
		Card(Rank.ACE, Suit.SPADES),
		Card(Rank.KING, Suit.HEARTS),
		Card(Rank.QUEEN, Suit.CLUBS),
		Card(Rank.JACK, Suit.DIAMONDS),
		Card(Rank.TEN, Suit.SPADES),
	])

	assert result.rank == HandRank.HIGH_CARD
