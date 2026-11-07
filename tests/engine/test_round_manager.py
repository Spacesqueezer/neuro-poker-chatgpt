from poker.game.round_manager import GameStreet, RoundManager


def test_round_starts_preflop():
	manager = RoundManager()

	assert manager.street == GameStreet.PREFLOP


def test_round_advances_streets():
	manager = RoundManager()

	assert manager.advance() == GameStreet.FLOP
	assert manager.advance() == GameStreet.TURN
	assert manager.advance() == GameStreet.RIVER
	assert manager.advance() == GameStreet.SHOWDOWN
