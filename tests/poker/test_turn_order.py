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


def test_turn_order_skips_folded_players():
	first = Player("Alice", 100)
	second = Player("Bob", 100)
	third = Player("Carol", 100)
	second.fold()

	order = TurnOrder([first, second, third])

	assert order.next_active_player() == third


def test_turn_order_can_set_position():
	players = [Player("Alice", 100), Player("Bob", 100), Player("Carol", 100)]
	order = TurnOrder(players)

	assert order.set_position(2) is players[2]
	assert order.current_player() is players[2]


def test_turn_order_can_start_after_position_and_skip_folded():
	players = [Player("Alice", 100), Player("Bob", 100), Player("Carol", 100)]
	players[1].fold()
	order = TurnOrder(players)

	assert order.set_to_next_active_after(0) is players[2]
