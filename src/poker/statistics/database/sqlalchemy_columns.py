from dataclasses import dataclass


@dataclass
class ColumnDefinition:
	name: str
	column_type: str
	nullable: bool = False
	primary_key: bool = False


PLAYER_COLUMNS = [
	ColumnDefinition(
		name="id",
		column_type="integer",
		primary_key=True,
	),
	ColumnDefinition(
		name="name",
		column_type="string",
	),
	ColumnDefinition(
		name="profile_id",
		column_type="integer",
		nullable=True,
	),
]


STATISTICS_COLUMNS = [
	ColumnDefinition(
		name="player_id",
		column_type="integer",
		primary_key=True,
	),
	ColumnDefinition(
		name="vpip",
		column_type="float",
	),
	ColumnDefinition(
		name="pfr",
		column_type="float",
	),
]


MEMORY_COLUMNS = [
	ColumnDefinition(
		name="agent_id",
		column_type="string",
		primary_key=True,
	),
	ColumnDefinition(
		name="player_id",
		column_type="integer",
		primary_key=True,
	),
]
