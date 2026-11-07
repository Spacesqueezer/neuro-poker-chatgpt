"""Remember explicit nickname corrections."""

import sqlalchemy as sa
from alembic import op

revision = "0007_hud_aliases"
down_revision = "0006_hud_observations"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "hud_aliases",
        sa.Column("alias_key", sa.String(256), primary_key=True),
        sa.Column(
            "player_key", sa.String(256), sa.ForeignKey("hud_players.player_key"), nullable=False
        ),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("corrected_at", sa.String(40), nullable=False),
    )


def downgrade():
    op.drop_table("hud_aliases")
