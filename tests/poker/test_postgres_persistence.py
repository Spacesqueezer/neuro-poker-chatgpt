from poker.statistics.database.postgres import PostgresConfig


def test_postgres_config():
	config = PostgresConfig(
		url="postgresql://localhost/poker"
	)

	assert config.url.startswith("postgresql")
