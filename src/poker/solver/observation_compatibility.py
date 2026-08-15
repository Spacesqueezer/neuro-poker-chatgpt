from dataclasses import dataclass


OBSERVATION_COMPATIBILITY_VERSION = 1
COMPATIBILITY_STATUSES = (
	"direct",
	"derived",
	"unavailable",
)


@dataclass(frozen=True)
class ObservationCompatibilityEntry:
	production_features: tuple[str, ...]
	status: str
	solver_sources: tuple[str, ...]
	reason: str


@dataclass(frozen=True)
class ObservationCompatibilityReport:
	version: int
	entries: tuple[ObservationCompatibilityEntry, ...]

	def by_status(self, status):
		if status not in COMPATIBILITY_STATUSES:
			raise ValueError(
				f"unsupported compatibility status: {status}"
			)
		return tuple(
			entry
			for entry in self.entries
			if entry.status == status
		)

	@property
	def unavailable_features(self):
		return tuple(
			feature
			for entry in self.by_status("unavailable")
			for feature in entry.production_features
		)


def build_observation_compatibility_report():
	entries = (
		ObservationCompatibilityEntry(
			production_features=("street.*",),
			status="direct",
			solver_sources=("street",),
			reason=(
				"Restricted information sets carry the same four public "
				"street semantics used by the production observation."
			),
		),
		ObservationCompatibilityEntry(
			production_features=("hole.*",),
			status="direct",
			solver_sources=("hole_cards",),
			reason=(
				"The acting player's two private cards are present; only "
				"card representation and one-hot encoding differ."
			),
		),
		ObservationCompatibilityEntry(
			production_features=("board.*",),
			status="direct",
			solver_sources=("public_board",),
			reason=(
				"Only currently public board cards are present in both "
				"schemas; future fixed-board cards remain hidden."
			),
		),
		ObservationCompatibilityEntry(
			production_features=(
				"hero.chips",
				"hero.total_contribution",
			),
			status="derived",
			solver_sources=(
				"player",
				"starting_stacks",
				"commitments",
			),
			reason=(
				"Remaining chips and total contribution can be derived "
				"from the acting player's public stack cap and commitment."
			),
		),
		ObservationCompatibilityEntry(
			production_features=(
				"opponent.0.present",
				"opponent.0.folded",
				"opponent.0.chips",
				"opponent.0.total_contribution",
			),
			status="derived",
			solver_sources=(
				"player",
				"starting_stacks",
				"commitments",
			),
			reason=(
				"Restricted Hold'em is heads-up. At a live decision node "
				"the other player is present and not folded; chips and "
				"total contribution derive from public stacks/commitments."
			),
		),
		ObservationCompatibilityEntry(
			production_features=("opponent.1-7.*",),
			status="derived",
			solver_sources=("player",),
			reason=(
				"Restricted Hold'em is always heads-up, so production "
				"opponent slots beyond slot 0 are structurally absent and "
				"would be zero-padded by the production encoder."
			),
		),
		ObservationCompatibilityEntry(
			production_features=(
				"table.pot",
				"table.target_bet",
				"hero.current_bet",
				"opponent.0.current_bet",
			),
			status="derived",
			solver_sources=(
				"street_commitments",
				"collected_pot",
			),
			reason=(
				"Street-local commitments and collected-pot state now "
				"preserve these production betting semantics explicitly."
			),
		),
		ObservationCompatibilityEntry(
			production_features=("table.minimum_raise",),
			status="derived",
			solver_sources=("minimum_raise",),
			reason=(
				"Restricted solver state now carries the public full-raise "
				"increment explicitly and resets it to the big blind on "
				"each new street."
			),
		),
		ObservationCompatibilityEntry(
			production_features=("opponent.0.profile.*",),
			status="unavailable",
			solver_sources=(),
			reason=(
				"Restricted solver records contain no persistent global, "
				"positional or agent-specific opponent profile data."
			),
		),
		ObservationCompatibilityEntry(
			production_features=(
				"metadata.acting_player",
				"metadata.opponent_order",
			),
			status="derived",
			solver_sources=("player",),
			reason=(
				"Restricted Hold'em has stable solver-local player indices. "
				"The bridge maps them deterministically to player_0/player_1 "
				"identity metadata and relative opponent order without claiming "
				"production table names."
			),
		),
	)

	for entry in entries:
		if entry.status not in COMPATIBILITY_STATUSES:
			raise ValueError(
				f"unsupported compatibility status: {entry.status}"
			)

	return ObservationCompatibilityReport(
		version=OBSERVATION_COMPATIBILITY_VERSION,
		entries=entries,
	)
