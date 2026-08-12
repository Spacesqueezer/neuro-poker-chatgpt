from poker.statistics.database.sqlalchemy_models import (
	DeclarativeBase,
	PlayerModel,
)


def test_declarative_base_exists():
	assert hasattr(DeclarativeBase, "metadata")
	assert issubclass(PlayerModel, DeclarativeBase)
