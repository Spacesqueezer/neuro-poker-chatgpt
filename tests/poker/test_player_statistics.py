from poker.statistics import PlayerStatistics


def test_player_statistics_basic_rates():
	stats = PlayerStatistics(
		player_name="Player_001",
		hands=100,
		vpip_hands=30,
		pfr_hands=20,
		showdowns=40,
		showdown_wins=20,
	)

	assert stats.vpip == 0.3
	assert stats.pfr == 0.2
	assert stats.wtsd == 0.4
	assert stats.wsd == 0.5
