from poker.statistics import HandStatisticsAdapter


def test_hand_adapter_updates_statistics():
	adapter = HandStatisticsAdapter()

	adapter.process_hand(
		{
			"players": [
				{
					"name": "Player_001",
					"entered_pot": True,
					"raised_preflop": True,
					"showdown": True,
					"won_showdown": True,
				}
			]
		}
	)

	stats = adapter.collector.get_player("Player_001")

	assert stats.hands == 1
	assert stats.vpip == 1
	assert stats.pfr == 1
