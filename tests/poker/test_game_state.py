from poker.game.game_state import GameState
from poker.player.player import Player


def test_game_state_creates_core_objects():
	state = GameState()

	assert state.deck is not None
	assert state.board is not None


def test_game_state_adds_players():
	state = GameState()
	player = Player("Alice", 100)

	state.add_player(player)

	assert state.player_count() == 1
	assert state.players[0] is player
	assert state.turn_order.current_player() is player


def test_game_state_reset():
	state = GameState()
	state.add_player(Player("Alice", 100))

	state.reset()

	assert state.player_count() == 0
