from poker.statistics.database.postgres import (
	PostgresConfig,
	PostgresSessionFactory,
)


def test_postgres_session_factory():
	factory = PostgresSessionFactory(
		PostgresConfig(
			url="postgresql://localhost/poker"
		)
	)

	session = factory.create()

	session.add("item")

	assert session.commit() is True
