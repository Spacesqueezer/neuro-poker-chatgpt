from poker.statistics.database.postgres_repositories import (
	PostgresMemoryRepository,
)


def test_postgres_repository_contract_exists():
	repository = PostgresMemoryRepository(None)

	assert hasattr(repository, "save")
	assert hasattr(repository, "get")
