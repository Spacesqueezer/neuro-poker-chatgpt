from poker.statistics import PlayerHandEvent


def test_player_hand_event_contract():
	event = PlayerHandEvent(
		player_name="Player_001",
		entered_pot=True,
		raised_preflop=True,
	)

	assert event.player_name == "Player_001"
	assert event.entered_pot is True
	assert event.raised_preflop is True
