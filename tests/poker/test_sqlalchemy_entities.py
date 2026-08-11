from poker.statistics.database.sqlalchemy_entities import (
	AgentMemoryEntity,
	PlayerEntity,
)


def test_entity_relationship_identity():
	player = PlayerEntity(
		id=1,
		name="Player_001",
	)

	memory = AgentMemoryEntity(
		agent_id="neural_a",
		player_id=player.id,
	)

	player.memories.append(memory)

	assert player.memories[0].player_id == player.id
