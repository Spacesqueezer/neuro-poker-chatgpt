from poker.statistics import StatisticsCollector


def test_statistics_collector_updates_player_rates():
	collector = StatisticsCollector()

	collector.register_hand(
		"Player_001",
		entered_pot=True,
		raised_preflop=True,
		showdown=True,
		won_showdown=True,
	)

	collector.register_hand(
		"Player_001",
		entered_pot=False,
	)

	stats = collector.get_player("Player_001")

	assert stats.hands == 2
	assert stats.vpip == 0.5
	assert stats.pfr == 0.5
	assert stats.wtsd == 0.5
	assert stats.wsd == 1
