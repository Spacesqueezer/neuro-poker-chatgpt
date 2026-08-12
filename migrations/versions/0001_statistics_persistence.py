"""Initial statistics persistence schema."""

from alembic import op
import sqlalchemy as sa


revision = "0001_statistics_persistence"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
	op.create_table(
		"players",
		sa.Column("id", sa.Integer(), nullable=False),
		sa.Column("name", sa.String(length=128), nullable=False),
		sa.Column("profile_id", sa.Integer(), nullable=True),
		sa.PrimaryKeyConstraint("id"),
	)

	op.create_table(
		"player_statistics",
		sa.Column("player_id", sa.Integer(), nullable=False),
		sa.Column("hands", sa.Integer(), nullable=False),
		sa.Column("vpip", sa.Float(), nullable=False),
		sa.Column("pfr", sa.Float(), nullable=False),
		sa.Column("three_bet", sa.Float(), nullable=False),
		sa.Column("aggression", sa.Float(), nullable=False),
		sa.Column("wtsd", sa.Float(), nullable=False),
		sa.Column("wsd", sa.Float(), nullable=False),
		sa.ForeignKeyConstraint(
			["player_id"],
			["players.id"],
			ondelete="CASCADE",
		),
		sa.PrimaryKeyConstraint("player_id"),
	)

	op.create_table(
		"agent_memory",
		sa.Column("agent_id", sa.String(length=128), nullable=False),
		sa.Column("player_id", sa.Integer(), nullable=False),
		sa.Column("hands_observed", sa.Integer(), nullable=False),
		sa.Column("vpip_estimate", sa.Float(), nullable=False),
		sa.Column("pfr_estimate", sa.Float(), nullable=False),
		sa.Column("aggression_estimate", sa.Float(), nullable=False),
		sa.Column("confidence", sa.Float(), nullable=False),
		sa.ForeignKeyConstraint(
			["player_id"],
			["players.id"],
			ondelete="CASCADE",
		),
		sa.PrimaryKeyConstraint(
			"agent_id",
			"player_id",
		),
	)


def downgrade() -> None:
	op.drop_table("agent_memory")
	op.drop_table("player_statistics")
	op.drop_table("players")
