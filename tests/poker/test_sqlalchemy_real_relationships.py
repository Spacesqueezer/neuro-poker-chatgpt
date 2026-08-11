from poker.statistics.database.sqlalchemy_real_relationships import (
	PlayerORM,
)


def test_relationships_exist():
	assert PlayerORM.statistics.property
	assert PlayerORM.memories.property
