import pytest

from poker.player.player import Player


def test_player_can_bet():
	player = Player("Alice", 100)

	player.bet(25)

	assert player.chips == 75
	assert player.current_bet == 25


def test_player_cannot_bet_more_than_stack():
	player = Player("Alice", 100)

	with pytest.raises(ValueError):
		player.bet(101)


def test_player_fold():
	player = Player("Alice", 100)

	player.fold()

	assert player.folded
