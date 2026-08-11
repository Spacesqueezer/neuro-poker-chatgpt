from poker.statistics.database.sqlalchemy_relationships import (
	AgentMemoryLink,
	PlayerWithRelations,
)


def test_relationship_models():
	player = PlayerWithRelations(
		id=1,
		name="Player_001",
	)

	link = AgentMemoryLink(
		agent_id="neural_a",
		player_id=player.id,
	)

	assert link.player_id == player.id
