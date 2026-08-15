import json

import pytest

from poker.solver import (
	MCCFRResult,
	build_strategy_export,
	build_teacher_record_export,
	write_teacher_record_export,
)
from tools.benchmark_mccfr import create_benchmark_game
from tools.export_solver_supervised_dataset import (
	export_solver_supervised_dataset,
	load_encoded_profiles,
)


def _teacher_payload():
	game = create_benchmark_game("equal")
	root = game.initial_nodes()[0].state
	player = game.player_to_act(root)
	information_set = game.information_set_for_node(root, player)
	strategy = build_strategy_export(
		MCCFRResult(
			iterations=1,
			average_strategy={
				information_set: {
					"fold": 0.1,
					"call": 0.2,
					"raise": 0.6,
					"all_in": 0.1,
				},
			},
			cumulative_regret={},
		),
		game,
		seed=42,
		scenario="equal",
		benchmark_version=2,
	)
	return build_teacher_record_export(strategy, game)


def _write_profiles(path):
	path.write_text(
		json.dumps(
			{
				"player_0": [float(index) for index in range(22)],
				"player_1": [float(index + 100) for index in range(22)],
			},
			sort_keys=True,
		),
		encoding="utf-8",
	)


def test_export_solver_supervised_dataset_is_deterministic_and_records_provenance(tmp_path):
	teacher_path = tmp_path / "teacher.json"
	profiles_path = tmp_path / "profiles.json"
	output = tmp_path / "solver.jsonl"
	manifest_path = tmp_path / "solver.manifest.json"
	teacher = _teacher_payload()
	write_teacher_record_export(teacher, teacher_path)
	_write_profiles(profiles_path)

	first = export_solver_supervised_dataset(
		teacher_path,
		profiles_path,
		output,
		manifest_output=manifest_path,
	)
	first_dataset = output.read_text(encoding="utf-8")
	first_manifest = manifest_path.read_text(encoding="utf-8")

	second = export_solver_supervised_dataset(
		teacher_path,
		profiles_path,
		output,
		manifest_output=manifest_path,
	)

	assert second == first
	assert output.read_text(encoding="utf-8") == first_dataset
	assert manifest_path.read_text(encoding="utf-8") == first_manifest
	assert first["format_version"] == 1
	assert first["sample_version"] == 1
	assert first["sample_count"] == teacher["record_count"]
	assert first["source_teacher"]["source_strategy"] == teacher[
		"source_strategy"
	]
	assert first["analysis"]["samples"] == teacher["record_count"]
	assert first["analysis"]["observation_sizes"] == {
		330: teacher["record_count"]
	}


def test_export_solver_supervised_dataset_uses_default_manifest_path(tmp_path):
	teacher_path = tmp_path / "teacher.json"
	profiles_path = tmp_path / "profiles.json"
	output = tmp_path / "solver.jsonl"
	write_teacher_record_export(_teacher_payload(), teacher_path)
	_write_profiles(profiles_path)

	export_solver_supervised_dataset(
		teacher_path,
		profiles_path,
		output,
	)

	assert output.with_suffix(".jsonl.manifest.json").exists()


def test_load_encoded_profiles_rejects_wrong_shape(tmp_path):
	profiles_path = tmp_path / "profiles.json"
	profiles_path.write_text(
		json.dumps(
			{
				"player_0": [0.0],
				"player_1": [0.0] * 22,
			}
		),
		encoding="utf-8",
	)

	with pytest.raises(
		ValueError,
		match="encoded profile for player_0 is invalid",
	):
		load_encoded_profiles(profiles_path)
