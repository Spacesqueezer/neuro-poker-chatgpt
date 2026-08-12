from poker.statistics.database.sqlalchemy_backend import (
	SQLAlchemyConfig,
	SQLAlchemyEngine,
)


def test_sqlalchemy_backend_boundary():
	engine = SQLAlchemyEngine(
		SQLAlchemyConfig(
			url="sqlite:///:memory:"
		)
	)

	session = engine.create_session()

	session.add("item")

	assert session.commit() is True
