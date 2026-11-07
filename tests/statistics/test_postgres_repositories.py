from poker.statistics.database.sqlalchemy_repositories import (
	SQLAlchemyMemoryRepository,
)


def test_postgres_repository_contract_exists():
	repository = SQLAlchemyMemoryRepository(None)

	assert hasattr(repository, "save")
	assert hasattr(repository, "get")
