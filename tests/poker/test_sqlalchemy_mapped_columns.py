from sqlalchemy import inspect

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
	assert inspect(PlayerModel).columns["id"].primary_key is True
	assert inspect(AgentMemoryModel).columns["agent_id"].primary_key is True
