from poker.cards.deck import Deck


def test_deck_has_52_cards():
	deck = Deck()

	assert len(deck.cards) == 52


def test_draw_removes_card():
	deck = Deck()

	deck.draw()

	assert len(deck.cards) == 51


def test_cards_are_unique():
	deck = Deck()

	assert len(set(deck.cards)) == 52
