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
