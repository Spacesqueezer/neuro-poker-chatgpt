from poker.statistics.database import (
	AgentMemoryRecord,
	PlayerRecord,
)


def test_database_models_store_identity():
	player = PlayerRecord(id=1, name="Player_001")
	memory = AgentMemoryRecord(
		agent_id="neural_a",
		player_id=player.id,
	)

	assert memory.player_id == 1
	assert memory.agent_id == "neural_a"
