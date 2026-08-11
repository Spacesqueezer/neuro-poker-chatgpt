from poker.statistics.database.sql import DatabaseConfig


def test_database_config():
	config = DatabaseConfig(
		url="postgresql://localhost/poker"
	)

	assert config.url.startswith("postgresql")
