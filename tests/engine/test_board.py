import pytest

from poker.board.board import Board
from poker.cards.card import Card
from poker.enums import Rank, Suit


def test_board_accepts_five_cards():
	board = Board()

	for _ in range(5):
		board.add_card(Card(Rank.ACE, Suit.SPADES))

	assert board.is_complete()


def test_board_cannot_have_six_cards():
	with pytest.raises(ValueError):
		Board([
			Card(Rank.ACE, Suit.SPADES),
			Card(Rank.KING, Suit.HEARTS),
			Card(Rank.QUEEN, Suit.CLUBS),
			Card(Rank.JACK, Suit.DIAMONDS),
			Card(Rank.TEN, Suit.SPADES),
			Card(Rank.NINE, Suit.HEARTS),
		])
