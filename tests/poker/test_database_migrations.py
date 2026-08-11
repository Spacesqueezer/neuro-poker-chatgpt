from poker.statistics.database.migrations import (
	MigrationConfig,
	MigrationRegistry,
)


def test_migration_registry():
	config = MigrationConfig(
		database_url="postgresql://localhost/poker"
	)

	registry = MigrationRegistry()
	registry.register("001_initial")

	assert config.database_url.startswith("postgresql")
	assert registry.latest() == "001_initial"
