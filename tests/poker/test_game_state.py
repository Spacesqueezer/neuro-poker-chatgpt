from poker.game.game_state import GameState
from poker.game.table import SeatStatus
from poker.player.player import Player


def test_game_state_creates_core_objects():
	state = GameState()

	assert state.deck is not None
	assert state.board is not None
	assert state.table is not None


def test_game_state_adds_players_to_table_and_hand_view():
	state = GameState()
	player = Player("Alice", 100)

	state.add_player(player)

	assert state.player_count() == 1
	assert state.players[0] is player
	assert state.table.seats[0].player is player
	assert state.turn_order.current_player() is player


def test_game_state_advances_dealer_button_and_wraps():
	state = GameState()
	state.add_player(Player("Alice", 100))
	state.add_player(Player("Bob", 100))
	state.add_player(Player("Carol", 100))

	assert state.advance_dealer_button() == 0
	assert state.advance_dealer_button() == 1
	assert state.advance_dealer_button() == 2
	assert state.advance_dealer_button() == 0


def test_prepare_for_hand_excludes_busted_player_without_removing_seat():
	state = GameState()
	alice = Player("Alice", 205)
	bob = Player("Bob", 95)
	carol = Player("Carol", 0)
	for player in (alice, bob, carol):
		state.add_player(player)

	state.prepare_for_hand()

	assert state.players == [alice, bob]
	assert [seat.player for seat in state.table.seats] == [alice, bob, carol]
	assert state.table.seat_for_player(carol).status == SeatStatus.BUSTED


def test_button_moves_from_old_seat_to_next_funded_seat_after_bust():
	state = GameState()
	alice = Player("Alice", 100)
	bob = Player("Bob", 100)
	carol = Player("Carol", 100)
	for player in (alice, bob, carol):
		state.add_player(player)

	state.advance_dealer_button()
	assert state.table.button_player() is alice
	bob.chips = 0

	state.prepare_for_hand()
	state.advance_dealer_button()

	assert state.players == [alice, carol]
	assert state.table.button_player() is carol
	assert state.players[state.dealer_button_index] is carol


def test_prepare_for_hand_rejects_one_funded_player():
	state = GameState()
	state.add_player(Player("Alice", 100))
	state.add_player(Player("Bob", 0))

	try:
		state.prepare_for_hand()
	except ValueError as error:
		assert "Not enough active players" in str(error)
	else:
		raise AssertionError("Expected prepare_for_hand to reject one funded player")


def test_game_state_reset_clears_table_and_players():
	state = GameState()
	state.add_player(Player("Alice", 100))
	state.advance_dealer_button()

	state.reset()

	assert state.player_count() == 0
	assert state.table.seats == []
	assert state.dealer_button_index is None


def test_sit_out_applies_to_next_hand_without_mutating_current_hand_view():
	state = GameState()
	alice = Player("Alice", 100)
	bob = Player("Bob", 100)
	carol = Player("Carol", 100)
	for player in (alice, bob, carol):
		state.add_player(player)

	state.sit_out(bob)

	assert state.players == [alice, bob, carol]
	state.prepare_for_hand()
	assert state.players == [alice, carol]
	assert state.table.seat_for_player(bob).status == SeatStatus.SITTING_OUT
