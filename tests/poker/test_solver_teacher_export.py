import json

from poker.solver import (
	MCCFRResult,
	build_strategy_export,
	build_teacher_record_export,
	load_teacher_record_export,
	validate_teacher_record_compatibility,
	validate_teacher_record_export,
	write_teacher_record_export,
)
from tools.benchmark_mccfr import create_benchmark_game


def build_payload(game, strategies, scenario="equal"):
	return build_strategy_export(
		MCCFRResult(
			iterations=1,
			average_strategy=strategies,
			cumulative_regret={},
		),
		game,
		seed=42,
		scenario=scenario,
		benchmark_version=2,
	)


def test_teacher_export_emits_only_stored_live_information_sets():
	game = create_benchmark_game("equal")
	root = game.initial_nodes()[0].state
	root_info = game.information_set_for_node(root, 0)
	payload = build_payload(
		game,
		{
			root_info: {
				"fold": 0.1,
				"call": 0.2,
				"raise": 0.6,
				"all_in": 0.1,
			},
		},
	)

	report = build_teacher_record_export(payload, game)

	assert report["format_version"] == 1
	assert report["record_count"] == 1
	assert report["skipped_missing_information_sets"] > 0
	assert report["skipped_zero_overlap_information_sets"] == 0
	assert report["records"][0]["source"] == "exact"
	assert report["records"][0]["legal_actions"] == [
		"fold",
		"call",
		"raise",
		"all_in",
	]
	assert report["records"][0]["action_probabilities"] == {
		"fold": 0.1,
		"call": 0.2,
		"raise": 0.6,
		"all_in": 0.1,
	}


def test_teacher_export_reconciles_stored_actions_without_fallback_labels():
	game = create_benchmark_game("equal")
	root = game.initial_nodes()[0].state
	root_info = game.information_set_for_node(root, 0)
	payload = build_payload(
		game,
		{
			root_info: {
				"fold": 0.25,
				"call": 0.25,
				"raise": 0.25,
				"all_in": 0.0,
				"obsolete": 0.25,
			},
		},
	)

	report = build_teacher_record_export(payload, game)
	record = report["records"][0]

	assert report["record_count"] == 1
	assert record["source"] == "reconciled"
	assert "obsolete" not in record["action_probabilities"]
	assert abs(
		sum(record["action_probabilities"].values()) - 1.0
	) < 1e-12


def test_teacher_export_skips_zero_legal_overlap():
	game = create_benchmark_game("equal")
	root = game.initial_nodes()[0].state
	root_info = game.information_set_for_node(root, 0)
	payload = build_payload(
		game,
		{
			root_info: {
				"obsolete": 1.0,
			},
		},
	)

	report = build_teacher_record_export(payload, game)

	assert report["record_count"] == 0
	assert report["skipped_zero_overlap_information_sets"] == 1
	assert report["records"] == []


def test_teacher_export_is_deterministic_and_writable(tmp_path):
	game = create_benchmark_game("weighted_multi")
	root = game.initial_nodes()[0].state
	root_info = game.information_set_for_node(root, 0)
	payload = build_payload(
		game,
		{
			root_info: {
				"fold": 0.25,
				"call": 0.25,
				"raise": 0.25,
				"all_in": 0.25,
			},
		},
		scenario="weighted_multi",
	)

	first = build_teacher_record_export(payload, game)
	second = build_teacher_record_export(payload, game)

	assert first == second
	assert first["source_strategy"]["benchmark"][
		"chance_space"
	]["identity"].startswith("sha256:")

	output = tmp_path / "teacher_records.json"
	write_teacher_record_export(first, output)
	assert json.loads(output.read_text(encoding="utf-8")) == first
	assert load_teacher_record_export(output) == first
	validate_teacher_record_compatibility(
		first,
		payload,
		game,
	)


def test_teacher_export_validation_rejects_bad_probability_sum():
	game = create_benchmark_game("equal")
	root = game.initial_nodes()[0].state
	root_info = game.information_set_for_node(root, 0)
	payload = build_payload(
		game,
		{
			root_info: {
				"fold": 0.25,
				"call": 0.25,
				"raise": 0.25,
				"all_in": 0.25,
			},
		},
	)
	teacher = build_teacher_record_export(payload, game)
	teacher["records"][0]["action_probabilities"]["fold"] = 0.5

	try:
		validate_teacher_record_export(teacher)
	except ValueError as error:
		assert "sum to 1" in str(error)
	else:
		raise AssertionError(
			"invalid teacher probability sum must fail validation"
		)


def test_teacher_export_validation_rejects_duplicate_information_sets():
	game = create_benchmark_game("equal")
	root = game.initial_nodes()[0].state
	root_info = game.information_set_for_node(root, 0)
	payload = build_payload(
		game,
		{
			root_info: {
				"fold": 0.25,
				"call": 0.25,
				"raise": 0.25,
				"all_in": 0.25,
			},
		},
	)
	teacher = build_teacher_record_export(payload, game)
	teacher["records"].append(
		json.loads(json.dumps(teacher["records"][0]))
	)
	teacher["record_count"] = 2

	try:
		validate_teacher_record_export(teacher)
	except ValueError as error:
		assert "duplicate" in str(error)
	else:
		raise AssertionError(
			"duplicate teacher information sets must fail validation"
		)


def test_teacher_export_compatibility_rejects_different_strategy():
	game = create_benchmark_game("equal")
	root = game.initial_nodes()[0].state
	root_info = game.information_set_for_node(root, 0)
	payload = build_payload(
		game,
		{
			root_info: {
				"fold": 0.25,
				"call": 0.25,
				"raise": 0.25,
				"all_in": 0.25,
			},
		},
	)
	teacher = build_teacher_record_export(payload, game)
	other = json.loads(json.dumps(payload))
	other["seed"] = 99

	try:
		validate_teacher_record_compatibility(
			teacher,
			other,
			game,
		)
	except ValueError as error:
		assert "source_strategy" in str(error)
	else:
		raise AssertionError(
			"teacher/source strategy mismatch must fail validation"
		)


def test_teacher_export_compatibility_rejects_wrong_chance_space():
	game = create_benchmark_game("weighted_multi")
	root = game.initial_nodes()[0].state
	root_info = game.information_set_for_node(root, 0)
	payload = build_payload(
		game,
		{
			root_info: {
				"fold": 0.25,
				"call": 0.25,
				"raise": 0.25,
				"all_in": 0.25,
			},
		},
		scenario="weighted_multi",
	)
	teacher = build_teacher_record_export(payload, game)
	payload["benchmark"]["chance_space"]["identity"] = (
		"sha256:" + ("0" * 64)
	)

	try:
		validate_teacher_record_compatibility(
			teacher,
			payload,
			game,
		)
	except ValueError as error:
		assert "chance_space" in str(error)
	else:
		raise AssertionError(
			"teacher chance-space mismatch must fail validation"
		)
