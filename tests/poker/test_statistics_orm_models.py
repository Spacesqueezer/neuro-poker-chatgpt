from poker.statistics.database.orm_models import (
	AgentMemoryORM,
	PlayerORM,
)


def test_orm_models_keep_relations():
	player = PlayerORM(
		id=1,
		name="Player_001",
	)

	memory = AgentMemoryORM(
		agent_id="neural_a",
		player_id=player.id,
	)

	assert memory.player_id == player.id
	assert memory.agent_id == "neural_a"
