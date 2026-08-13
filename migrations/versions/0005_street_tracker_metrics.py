"""Persist fold-to-cbet and street-specific aggression counters."""

from alembic import op
import sqlalchemy as sa


revision = "0005_street_tracker_metrics"
down_revision = "0004_position_statistics"
branch_labels = None
depends_on = None


_COLUMNS = (
	"fold_to_cbet_opportunities",
	"folds_to_cbet",
	"flop_aggressive_actions",
	"flop_calls",
	"turn_aggressive_actions",
	"turn_calls",
	"river_aggressive_actions",
	"river_calls",
)


def upgrade() -> None:
	for column_name in _COLUMNS:
		op.add_column(
			"player_statistics",
			sa.Column(
				column_name,
				sa.Integer(),
				nullable=False,
				server_default="0",
			),
		)


def downgrade() -> None:
	for column_name in reversed(_COLUMNS):
		op.drop_column(
			"player_statistics",
			column_name,
		)
