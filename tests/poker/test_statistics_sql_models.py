from poker.statistics.database.sql_models import (
	AgentMemorySQLModel,
	PlayerSQLModel,
)


def test_sql_models_keep_identity():
	player = PlayerSQLModel(
		id=1,
		name="Player_001",
	)

	memory = AgentMemorySQLModel(
		agent_id="neural_a",
		player_id=player.id,
	)

	assert player.id == 1
	assert memory.player_id == 1
