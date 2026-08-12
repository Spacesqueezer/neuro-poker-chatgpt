from pathlib import Path

from sqlalchemy import create_engine, inspect

from poker.statistics.database.migrations import (
	MigrationConfig,
	downgrade_database,
	upgrade_database,
)


def test_initial_migration_round_trip(tmp_path):
	project_root = Path(__file__).resolve().parents[2]
	database_path = tmp_path / "poker.db"
	database_url = f"sqlite:///{database_path}"

	config = MigrationConfig(
		database_url=database_url,
		alembic_ini=str(project_root / "alembic.ini"),
	)

	upgrade_database(config)

	engine = create_engine(database_url)
	inspector = inspect(engine)

	assert {
		"players",
		"player_statistics",
		"agent_memory",
	}.issubset(set(inspector.get_table_names()))

	assert inspector.get_pk_constraint("agent_memory")["constrained_columns"] == [
		"agent_id",
		"player_id",
	]

	engine.dispose()

	downgrade_database(config)

	engine = create_engine(database_url)
	assert "players" not in inspect(engine).get_table_names()
	engine.dispose()
