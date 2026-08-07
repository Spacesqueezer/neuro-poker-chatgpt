from poker.game.turn_order import TurnOrder
from poker.player.player import Player


def test_turn_order_returns_first_player():
	first = Player("Alice", 100)
	second = Player("Bob", 100)

	order = TurnOrder([first, second])

	assert order.current_player() == first


def test_turn_order_moves_to_next_player():
	first = Player("Alice", 100)
	second = Player("Bob", 100)

	order = TurnOrder([first, second])

	assert order.next_player() == second


def test_turn_order_wraps_around():
	first = Player("Alice", 100)
	second = Player("Bob", 100)

	order = TurnOrder([first, second])

	order.next_player()
	assert order.next_player() == first
