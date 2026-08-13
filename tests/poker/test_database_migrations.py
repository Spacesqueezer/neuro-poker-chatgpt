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
		"player_position_statistics",
		"agent_memory",
	}.issubset(set(inspector.get_table_names()))

	player_statistics_columns = {
		column["name"]
		for column in inspector.get_columns("player_statistics")
	}
	assert {
		"fold_to_cbet_opportunities",
		"folds_to_cbet",
		"flop_aggressive_actions",
		"flop_calls",
		"turn_aggressive_actions",
		"turn_calls",
		"river_aggressive_actions",
		"river_calls",
	}.issubset(player_statistics_columns)

	assert inspector.get_pk_constraint("agent_memory")["constrained_columns"] == [
		"agent_id",
		"player_id",
	]

	player_unique_constraints = inspector.get_unique_constraints("players")
	assert any(
		constraint["column_names"] == ["name"]
		for constraint in player_unique_constraints
	)

	engine.dispose()

	downgrade_database(config)

	engine = create_engine(database_url)
	assert "players" not in inspect(engine).get_table_names()
	engine.dispose()
