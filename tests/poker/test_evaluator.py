from poker.cards.card import Card
from poker.enums import Rank, Suit
from poker.evaluation.evaluator import evaluate
from poker.evaluation.hand_rank import HandRank


def test_evaluator_returns_high_card():
	result = evaluate([
		Card(Rank.ACE, Suit.SPADES),
		Card(Rank.KING, Suit.HEARTS),
		Card(Rank.QUEEN, Suit.CLUBS),
		Card(Rank.JACK, Suit.DIAMONDS),
		Card(Rank.TEN, Suit.SPADES),
	])

	assert result.rank == HandRank.HIGH_CARD


def test_evaluator_detects_pair():
	result = evaluate([
		Card(Rank.ACE, Suit.SPADES),
		Card(Rank.ACE, Suit.HEARTS),
		Card(Rank.QUEEN, Suit.CLUBS),
		Card(Rank.JACK, Suit.DIAMONDS),
		Card(Rank.TEN, Suit.SPADES),
	])

	assert result.rank == HandRank.PAIR


def test_evaluator_detects_full_house():
	result = evaluate([
		Card(Rank.ACE, Suit.SPADES),
		Card(Rank.ACE, Suit.HEARTS),
		Card(Rank.ACE, Suit.CLUBS),
		Card(Rank.KING, Suit.DIAMONDS),
		Card(Rank.KING, Suit.SPADES),
	])

	assert result.rank == HandRank.FULL_HOUSE
