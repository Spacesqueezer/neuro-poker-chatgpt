from poker.cards.card import Card
from poker.enums import Rank, Suit
from poker.evaluation.evaluator import evaluate
from poker.evaluation.hand_rank import HandRank


def test_evaluator_returns_high_card():
	result = evaluate([
		Card(Rank.ACE, Suit.SPADES),
		Card(Rank.KING, Suit.HEARTS),
		Card(Rank.QUEEN, Suit.CLUBS),
		Card(Rank.NINE, Suit.DIAMONDS),
		Card(Rank.TWO, Suit.SPADES),
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


def test_evaluator_detects_straight_flush():
	result = evaluate([
		Card(Rank.ACE, Suit.SPADES),
		Card(Rank.KING, Suit.SPADES),
		Card(Rank.QUEEN, Suit.SPADES),
		Card(Rank.JACK, Suit.SPADES),
		Card(Rank.TEN, Suit.SPADES),
	])

	assert result.rank == HandRank.STRAIGHT_FLUSH


def test_evaluator_detects_straight():
	result = evaluate([
		Card(Rank.TEN, Suit.SPADES),
		Card(Rank.NINE, Suit.HEARTS),
		Card(Rank.EIGHT, Suit.CLUBS),
		Card(Rank.SEVEN, Suit.DIAMONDS),
		Card(Rank.SIX, Suit.SPADES),
	])

	assert result.rank == HandRank.STRAIGHT
