from poker.statistics import OpponentMemory


def test_opponent_memory_is_agent_specific():
	first = OpponentMemory(
		agent_id="neural_a",
		player_name="Player_001",
	)

	second = OpponentMemory(
		agent_id="neural_b",
		player_name="Player_001",
	)

	assert first.agent_id != second.agent_id
