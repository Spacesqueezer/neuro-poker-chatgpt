"""Require stable unique player names for roster resolution."""

from alembic import op


revision = "0003_unique_player_names"
down_revision = "0002_tracker_counters"
branch_labels = None
depends_on = None


def upgrade() -> None:
	with op.batch_alter_table("players") as batch_op:
		batch_op.create_unique_constraint(
			"uq_players_name",
			["name"],
		)


def downgrade() -> None:
	with op.batch_alter_table("players") as batch_op:
		batch_op.drop_constraint(
			"uq_players_name",
			type_="unique",
		)
