from poker.statistics.database.postgres import (
	PostgresConfig,
	PostgresEngine,
	PostgresSessionFactory,
)


def test_engine_boundary():
	factory = PostgresSessionFactory(
		PostgresConfig(
			url="postgresql://localhost/poker"
		)
	)

	session = factory.create()

	assert isinstance(session.engine, PostgresEngine)
