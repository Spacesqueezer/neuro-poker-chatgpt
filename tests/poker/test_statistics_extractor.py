from poker.statistics import HandStatisticsExtractor


def test_extractor_creates_player_events():
	extractor = HandStatisticsExtractor()

	events = extractor.extract(
		{
			"players": [
				{
					"name": "Player_001",
					"entered_pot": True,
					"raised_preflop": True,
				}
			]
		}
	)

	assert len(events) == 1
	assert events[0].player_name == "Player_001"
	assert events[0].entered_pot is True
