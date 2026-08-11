from poker.players import generate_player_pool


def test_player_pool_generation():
	players = generate_player_pool()

	assert len(players) == 70
	assert len({player.name for player in players}) == 70
	assert all(player.style for player in players)
