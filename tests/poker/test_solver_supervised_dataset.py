import json

import pytest

from poker.solver import (
	MCCFRResult,
	SOLVER_SUPERVISED_SAMPLE_VERSION,
	SolverSupervisedDatasetAnalyzer,
	SolverSupervisedDatasetWriter,
	build_learning_bridge_records,
	build_solver_supervised_samples,
	build_strategy_export,
	build_teacher_record_export,
)
from tools.benchmark_mccfr import create_benchmark_game


def _teacher(game, state, strategy):
	player = game.player_to_act(state)
	information_set = game.information_set_for_node(state, player)
	strategy_payload = build_strategy_export(
		MCCFRResult(
			iterations=1,
			average_strategy={information_set: strategy},
			cumulative_regret={},
		),
		game,
		seed=42,
		scenario="equal",
		benchmark_version=2,
	)
	return build_teacher_record_export(strategy_payload, game)


def _profiles():
	return {
		"player_0": tuple(float(index) for index in range(22)),
		"player_1": tuple(float(index + 100) for index in range(22)),
	}


def test_solver_supervised_sample_preserves_soft_target_and_numeric_observation():
	game = create_benchmark_game("equal")
	root = game.initial_nodes()[0].state
	teacher = _teacher(
		game,
		root,
		{
			"fold": 0.1,
			"call": 0.2,
			"raise": 0.6,
			"all_in": 0.1,
		},
	)
	record = build_learning_bridge_records(
		teacher,
		opponent_profiles=_profiles(),
	)[0]

	sample = build_solver_supervised_samples((record,))[0]

	assert sample.version == SOLVER_SUPERVISED_SAMPLE_VERSION == 1
	assert len(sample.observation) == 330
	assert sample.action_names == (
		"fold",
		"check",
		"call",
		"bet",
		"raise",
		"all_in",
	)
	assert sample.legal_mask == (
		1.0,
		0.0,
		1.0,
		0.0,
		1.0,
		1.0,
	)
	assert sample.probabilities == (
		0.1,
		0.0,
		0.2,
		0.0,
		0.6,
		0.1,
	)
	assert sample.acting_player == "player_0"
	assert sample.opponent_order == ("player_1",)
	assert sample.source == "exact"


def test_solver_supervised_dataset_round_trip_and_analysis(tmp_path):
	game = create_benchmark_game("equal")
	root = game.initial_nodes()[0].state
	teacher = _teacher(game, root, {"fold": 1.0})
	records = build_learning_bridge_records(
		teacher,
		opponent_profiles=_profiles(),
	)
	samples = build_solver_supervised_samples(records)
	path = tmp_path / "solver.jsonl"

	writer = SolverSupervisedDatasetWriter(path)
	assert writer.write_many(samples) == len(samples)

	lines = path.read_text(encoding="utf-8").splitlines()
	assert len(lines) == len(samples)
	assert json.loads(lines[0])["version"] == 1

	summary = SolverSupervisedDatasetAnalyzer().analyze(path)
	assert summary["samples"] == len(samples)
	assert summary["versions"] == {1: len(samples)}
	assert summary["observation_sizes"] == {330: len(samples)}
	assert summary["consistent_observation_size"] is True
	assert summary["acting_players"] == {"player_0": len(samples)}


def test_solver_supervised_dataset_rejects_missing_profile():
	game = create_benchmark_game("equal")
	root = game.initial_nodes()[0].state
	teacher = _teacher(game, root, {"fold": 1.0})
	record = build_learning_bridge_records(teacher)[0]

	with pytest.raises(
		ValueError,
		match="numeric bridge observation requires opponent_profile",
	):
		build_solver_supervised_samples((record,))


def test_solver_supervised_analyzer_rejects_probability_on_illegal_action(tmp_path):
	path = tmp_path / "broken.jsonl"
	payload = {
		"version": 1,
		"observation": [0.0],
		"action_names": [
			"fold",
			"check",
			"call",
			"bet",
			"raise",
			"all_in",
		],
		"legal_mask": [1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
		"probabilities": [0.5, 0.5, 0.0, 0.0, 0.0, 0.0],
		"solver_action_groups": [["fold"], [], [], [], [], []],
		"acting_player": "player_0",
		"opponent_order": ["player_1"],
		"source": "exact",
	}
	path.write_text(
		json.dumps(payload) + "\n",
		encoding="utf-8",
	)

	with pytest.raises(
		ValueError,
		match="probability assigned to illegal action",
	):
		SolverSupervisedDatasetAnalyzer().analyze(path)
