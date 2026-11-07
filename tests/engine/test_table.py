import pytest

from poker.game.table import SeatStatus, Table
from poker.player.player import Player


def test_table_keeps_busted_seat_while_excluding_player_from_next_hand():
	table = Table()
	alice = Player("Alice", 100)
	bob = Player("Bob", 0)
	table.add_player(alice)
	table.add_player(bob)

	assert table.hand_players() == [alice]
	assert table.seat_for_player(bob).status == SeatStatus.BUSTED
	assert len(table.seats) == 2


def test_button_skips_busted_and_sitting_out_seats():
	table = Table()
	alice = Player("Alice", 100)
	bob = Player("Bob", 100)
	carol = Player("Carol", 100)
	dave = Player("Dave", 100)
	for player in (alice, bob, carol, dave):
		table.add_player(player)

	table.set_button_player(alice)
	table.mark_busted(bob)
	table.sit_out(carol)

	assert table.advance_button() == 3
	assert table.button_player() is dave


def test_sitting_out_player_can_return_with_chips():
	table = Table()
	alice = Player("Alice", 100)
	table.add_player(alice)

	table.sit_out(alice)
	assert table.hand_players() == []

	table.sit_in(alice)
	assert table.hand_players() == [alice]


def test_busted_player_needs_chips_before_sitting_in():
	table = Table()
	alice = Player("Alice", 0)
	table.add_player(alice)
	table.sync_statuses()

	with pytest.raises(ValueError, match="needs chips"):
		table.sit_in(alice)
