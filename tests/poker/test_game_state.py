from poker.game.game_state import GameState


def test_game_state_creates_core_objects():
	state = GameState()

	assert state.deck is not None
	assert state.board is not None


def test_game_state_adds_players():
	state = GameState()

	state.add_player()

	assert state.player_count() == 1


def test_game_state_reset():
	state = GameState()

	state.add_player()
	state.reset()

	assert state.player_count() == 0
