"""Separate live HUD observations from simulation statistics."""

import sqlalchemy as sa
from alembic import op

revision = "0006_hud_observations"
down_revision = "0005_street_tracker_metrics"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "hud_players",
        sa.Column("player_key", sa.String(256), primary_key=True),
        sa.Column("room", sa.String(32), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("first_seen", sa.String(40), nullable=False),
        sa.Column("last_seen", sa.String(40), nullable=False),
    )
    op.create_table(
        "hud_hands",
        sa.Column("hand_key", sa.String(256), primary_key=True),
        sa.Column("client_id", sa.String(32), nullable=False),
        sa.Column("table_key", sa.String(128), nullable=False),
        sa.Column("observed_at", sa.String(40), nullable=False),
        sa.Column("hero_seen", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "hud_sightings",
        sa.Column(
            "hand_key", sa.String(256), sa.ForeignKey("hud_hands.hand_key"), primary_key=True
        ),
        sa.Column("source", sa.String(128), primary_key=True),
        sa.Column("seat", sa.Integer(), primary_key=True),
        sa.Column("player_key", sa.String(256), sa.ForeignKey("hud_players.player_key")),
        sa.Column("raw_name", sa.Text(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
    )
    op.create_index("ix_hud_sightings_player", "hud_sightings", ["player_key", "hand_key"])
    op.create_table(
        "hud_actions",
        sa.Column("event_id", sa.String(128), primary_key=True),
        sa.Column("hand_key", sa.String(256), sa.ForeignKey("hud_hands.hand_key"), nullable=False),
        sa.Column(
            "player_key", sa.String(256), sa.ForeignKey("hud_players.player_key"), nullable=False
        ),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
    )
    op.create_index("ix_hud_actions_player", "hud_actions", ["player_key"])


def downgrade():
    op.drop_table("hud_actions")
    op.drop_table("hud_sightings")
    op.drop_table("hud_hands")
    op.drop_table("hud_players")
