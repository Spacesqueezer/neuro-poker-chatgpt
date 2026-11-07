from poker.statistics.database.sqlalchemy_backend import (
	SQLAlchemyConfig,
	SQLAlchemyEngine,
)
from poker.statistics.database.sqlalchemy_models import PlayerModel


def test_sqlalchemy_backend_boundary():
	engine = SQLAlchemyEngine(
		SQLAlchemyConfig(
			url="sqlite:///:memory:",
			create_schema=True,
		)
	)

	with engine.create_session() as session:
		session.add(
			PlayerModel(
				id=1,
				name="Player_001",
			)
		)
		session.commit()

		assert session.get(PlayerModel, 1).name == "Player_001"

	engine.dispose()
