from poker.game.betting import BettingState


def test_betting_adds_to_pot():
	state = BettingState()

	state.add_bet(50)

	assert state.pot == 50
	assert state.current_bet == 50


def test_betting_round_reset():
	state = BettingState()

	state.add_bet(50)
	state.reset_round()

	assert state.current_bet == 0


def test_collect_player_bet():
	from poker.player.player import Player

	state = BettingState()
	player = Player("Alice", 100)

	player.bet(50)
	state.collect_player_bet(player)

	assert state.pot == 50
	assert player.current_bet == 0
