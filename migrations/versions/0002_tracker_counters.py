"""Persist tracker statistic numerators and denominators."""

from alembic import op
import sqlalchemy as sa


revision = "0002_tracker_counters"
down_revision = "0001_statistics_persistence"
branch_labels = None
depends_on = None


_COLUMNS = (
	"vpip_hands",
	"pfr_hands",
	"three_bet_opportunities",
	"three_bets",
	"fold_to_three_bet_opportunities",
	"folds_to_three_bet",
	"cbet_opportunities",
	"cbets",
	"aggressive_actions",
	"calls",
	"showdowns",
	"showdown_wins",
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
