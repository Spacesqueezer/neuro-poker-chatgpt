from poker.statistics.database.orm_tables import (
	AgentMemoryTable,
	PlayerTable,
)


def test_table_models_preserve_identity():
	player = PlayerTable(
		id=1,
		name="Player_001",
	)

	memory = AgentMemoryTable(
		agent_id="neural_a",
		player_id=player.id,
	)

	assert memory.player_id == player.id
	assert memory.agent_id == "neural_a"
