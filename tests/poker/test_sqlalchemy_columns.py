from poker.statistics.database.sqlalchemy_columns import (
	MEMORY_COLUMNS,
	PLAYER_COLUMNS,
)


def test_column_definitions():
	assert PLAYER_COLUMNS[0].primary_key is True
	assert MEMORY_COLUMNS[0].primary_key is True
