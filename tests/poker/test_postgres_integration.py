import os

import pytest
from sqlalchemy import create_engine, inspect, text

from poker.statistics.database.migrations import (
	MigrationConfig,
	downgrade_database,
	upgrade_database,
)
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


POSTGRES_TEST_URL = os.environ.get("POKER_TEST_DATABASE_URL")


pytestmark = pytest.mark.skipif(
	not POSTGRES_TEST_URL,
	reason="POKER_TEST_DATABASE_URL is not configured",
)


def _migration_config() -> MigrationConfig:
	return MigrationConfig(
		database_url=POSTGRES_TEST_URL,
	)


def _reset_database() -> None:
	downgrade_database(
		_migration_config(),
		revision="base",
	)
	upgrade_database(_migration_config())


def test_postgres_migrations_and_repository_round_trip():
	_reset_database()

	engine = create_engine(POSTGRES_TEST_URL)
	try:
		table_names = set(inspect(engine).get_table_names())
		assert {
			"players",
			"player_statistics",
			"agent_memory",
			"alembic_version",
		}.issubset(table_names)
	finally:
		engine.dispose()

	backend = SQLAlchemyEngine(
		SQLAlchemyConfig(
			url=POSTGRES_TEST_URL,
			create_schema=False,
		)
	)

	try:
		with backend.create_session() as session:
			players = PostgresPlayerRepository(session)
			statistics = PostgresStatisticsRepository(session)
			memory = PostgresMemoryRepository(session)

			player = PlayerRecord(
				id=900001,
				name="Postgres_Test_Player",
			)
			player_stats = PlayerStatisticsRecord(
				player_id=player.id,
				hands=250,
				vpip=0.28,
				pfr=0.19,
				three_bet=0.07,
				aggression=2.2,
				wtsd=0.25,
				wsd=0.51,
			)
			agent_memory = AgentMemoryRecord(
				agent_id="postgres_test_agent",
				player_id=player.id,
				hands_observed=125,
				vpip_estimate=0.27,
				pfr_estimate=0.18,
				aggression_estimate=2.0,
				confidence=0.82,
			)

			players.save(player)
			statistics.save(player_stats)
			memory.save(agent_memory)

			assert players.get(player.id) == player
			assert statistics.get(player.id) == player_stats
			assert memory.get(agent_memory.agent_id, player.id) == agent_memory

			session.execute(
				text("DELETE FROM agent_memory WHERE player_id = :player_id"),
				{"player_id": player.id},
			)
			session.execute(
				text("DELETE FROM player_statistics WHERE player_id = :player_id"),
				{"player_id": player.id},
			)
			session.execute(
				text("DELETE FROM players WHERE id = :player_id"),
				{"player_id": player.id},
			)
			session.commit()
	finally:
		backend.dispose()
