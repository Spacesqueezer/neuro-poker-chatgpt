"""Persist positional tracker statistics."""

from alembic import op
import sqlalchemy as sa


revision = "0004_position_statistics"
down_revision = "0003_unique_player_names"
branch_labels = None
depends_on = None


def upgrade() -> None:
	op.create_table(
		"player_position_statistics",
		sa.Column("player_id", sa.Integer(), nullable=False),
		sa.Column("position", sa.String(length=16), nullable=False),
		sa.Column("hands", sa.Integer(), nullable=False),
		sa.Column("vpip", sa.Float(), nullable=False),
		sa.Column("pfr", sa.Float(), nullable=False),
		sa.Column("three_bet", sa.Float(), nullable=False),
		sa.Column("vpip_hands", sa.Integer(), nullable=False),
		sa.Column("pfr_hands", sa.Integer(), nullable=False),
		sa.Column("three_bet_opportunities", sa.Integer(), nullable=False),
		sa.Column("three_bets", sa.Integer(), nullable=False),
		sa.ForeignKeyConstraint(
			["player_id"],
			["players.id"],
			ondelete="CASCADE",
		),
		sa.PrimaryKeyConstraint(
			"player_id",
			"position",
		),
	)


def downgrade() -> None:
	op.drop_table("player_position_statistics")
