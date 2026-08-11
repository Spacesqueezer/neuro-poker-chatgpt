from poker.statistics import HandStatisticsMapper


def test_hand_mapping_keeps_statistics_contract():
	mapper = HandStatisticsMapper()

	result = mapper.map_hand(
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

	assert result["players"][0]["name"] == "Player_001"
	assert result["players"][0]["entered_pot"] is True
