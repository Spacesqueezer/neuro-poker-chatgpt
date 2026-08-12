from poker.statistics.database.sqlalchemy_models import (
	AgentMemoryModel,
	PlayerModel,
)


def test_mapped_metadata_preserves_constructor_contract():
	player = PlayerModel(
		id=1,
		name="Player_001",
	)

	assert player.id == 1
	assert PlayerModel.__mapped_fields__["id"].primary_key is True
	assert AgentMemoryModel.__mapped_fields__["agent_id"].primary_key is True
