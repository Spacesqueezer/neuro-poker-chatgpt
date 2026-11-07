from poker.statistics.database.sqlalchemy_models import (
	AgentMemoryModel,
	PlayerModel,
)


def test_sqlalchemy_models_keep_relations():
	player = PlayerModel(
		id=1,
		name="Player_001",
	)

	memory = AgentMemoryModel(
		agent_id="neural_a",
		player_id=player.id,
	)

	assert memory.player_id == player.id
