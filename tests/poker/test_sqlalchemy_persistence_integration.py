from poker.statistics.database.models import (
	AgentMemoryRecord,
	PlayerRecord,
	PlayerStatisticsRecord,
)
from poker.statistics.database.postgres_repositories import (
	PostgresMemoryRepository,
	PostgresPlayerRepository,
	PostgresStatisticsRepository,
)
from poker.statistics.database.sqlalchemy_backend import (
	SQLAlchemyConfig,
	SQLAlchemyEngine,
)


def test_sqlalchemy_repositories_round_trip_records():
	engine = SQLAlchemyEngine(
		SQLAlchemyConfig(
			url="sqlite:///:memory:",
			create_schema=True,
		)
	)

	with engine.create_session() as session:
		players = PostgresPlayerRepository(session)
		statistics = PostgresStatisticsRepository(session)
		memory = PostgresMemoryRepository(session)

		player = PlayerRecord(
			id=1,
			name="Player_001",
		)
		player_stats = PlayerStatisticsRecord(
			player_id=1,
			hands=100,
			vpip=0.31,
			pfr=0.22,
			three_bet=0.08,
			aggression=2.4,
			wtsd=0.27,
			wsd=0.53,
		)
		agent_memory = AgentMemoryRecord(
			agent_id="neural_a",
			player_id=1,
			hands_observed=40,
			vpip_estimate=0.29,
			pfr_estimate=0.20,
			aggression_estimate=2.1,
			confidence=0.75,
		)

		players.save(player)
		statistics.save(player_stats)
		memory.save(agent_memory)

		assert players.get(1) == player
		assert statistics.get(1) == player_stats
		assert memory.get("neural_a", 1) == agent_memory
		assert memory.get("neural_b", 1) is None

	engine.dispose()
