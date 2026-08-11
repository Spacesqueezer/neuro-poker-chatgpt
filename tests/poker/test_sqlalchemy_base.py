from poker.statistics.database.sqlalchemy_base import (
	Base,
	ORMEngineConfig,
)


def test_sqlalchemy_base_contract():
	config = ORMEngineConfig(
		url="postgresql://localhost/poker",
	)

	assert Base
	assert config.echo is False
