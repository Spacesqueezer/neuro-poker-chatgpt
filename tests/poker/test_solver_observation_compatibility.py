from poker.learning.observation import (
	CARD_INDEX,
	STREETS,
	LearningObservationEncoder,
)
from poker.solver import (
	COMPATIBILITY_STATUSES,
	build_observation_compatibility_report,
)


def test_observation_compatibility_report_has_explicit_statuses():
	report = build_observation_compatibility_report()

	assert report.version == 1
	assert COMPATIBILITY_STATUSES == (
		"direct",
		"derived",
		"unavailable",
	)
	assert report.by_status("direct")
	assert report.by_status("derived")
	assert report.by_status("unavailable")


def test_observation_compatibility_covers_production_schema_groups():
	report = build_observation_compatibility_report()
	features = {
		feature
		for entry in report.entries
		for feature in entry.production_features
	}

	assert "street.*" in features
	assert "hole.*" in features
	assert "board.*" in features
	assert "table.pot" in features
	assert "table.target_bet" in features
	assert "table.minimum_raise" in features
	assert "hero.chips" in features
	assert "hero.current_bet" in features
	assert "hero.total_contribution" in features
	assert "opponent.0.present" in features
	assert "opponent.0.folded" in features
	assert "opponent.0.chips" in features
	assert "opponent.0.current_bet" in features
	assert "opponent.0.total_contribution" in features
	assert "opponent.0.profile.*" in features
	assert "opponent.1-7.*" in features
	assert "metadata.acting_player" in features
	assert "metadata.opponent_order" in features


def test_direct_card_and_street_semantics_match_current_encoder_shape():
	report = build_observation_compatibility_report()
	direct = {
		feature
		for entry in report.by_status("direct")
		for feature in entry.production_features
	}

	assert "street.*" in direct
	assert "hole.*" in direct
	assert "board.*" in direct
	assert tuple(STREETS) == (
		"preflop",
		"flop",
		"turn",
		"river",
	)
	assert len(CARD_INDEX) == 52


def test_unavailable_features_are_not_silently_claimed_as_derivable():
	report = build_observation_compatibility_report()

	assert "table.pot" not in report.unavailable_features
	assert "table.target_bet" not in report.unavailable_features
	assert "table.minimum_raise" in report.unavailable_features
	assert "hero.current_bet" not in report.unavailable_features
	assert "opponent.0.current_bet" not in report.unavailable_features
	assert "opponent.0.profile.*" in report.unavailable_features
	assert "metadata.acting_player" in report.unavailable_features
	assert "metadata.opponent_order" in report.unavailable_features


def test_report_tracks_current_production_opponent_slot_count():
	report = build_observation_compatibility_report()
	derived = {
		feature
		for entry in report.by_status("derived")
		for feature in entry.production_features
	}

	assert LearningObservationEncoder.MAX_OPPONENTS == 8
	assert "opponent.0.present" in derived
	assert "opponent.1-7.*" in derived
