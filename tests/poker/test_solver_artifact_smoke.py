import json

import pytest

from poker.solver import load_strategy_export
from tools.smoke_solver_artifacts import run_smoke


def test_solver_artifact_smoke_runs_equal_and_asymmetric_round_trip(
	tmp_path,
):
	report = run_smoke(
		tmp_path,
		iterations=1,
		seed=7,
	)

	assert report["smoke_report_version"] == 1
	assert report["iterations"] == 1
	assert report["seed"] == 7
	assert [
		item["scenario"]
		for item in report["scenarios"]
	] == ["equal", "asymmetric"]

	for item in report["scenarios"]:
		assert item["artifact_round_trip"]
		assert item["information_set_count"] > 0
		assert item["evaluation"]["decision_nodes"] > 0
		assert item["evaluation"]["terminal_nodes"] > 0

		strategy_path = tmp_path / item["strategy_file"]
		assert strategy_path.exists()
		loaded = load_strategy_export(strategy_path)
		assert loaded["benchmark"]["scenario"] == item["scenario"]

	saved_report = json.loads(
		(tmp_path / "smoke_report.json").read_text(
			encoding="utf-8"
		)
	)
	assert saved_report == report


def test_solver_artifact_smoke_report_is_reproducible_for_fixed_seed(
	tmp_path,
):
	first = run_smoke(
		tmp_path / "first",
		iterations=1,
		seed=11,
		scenarios=("asymmetric",),
	)
	second = run_smoke(
		tmp_path / "second",
		iterations=1,
		seed=11,
		scenarios=("asymmetric",),
	)

	assert first == second


def test_solver_artifact_smoke_rejects_invalid_workload(tmp_path):
	with pytest.raises(
		ValueError,
		match="iterations must be positive",
	):
		run_smoke(
			tmp_path,
			iterations=0,
		)

	with pytest.raises(
		ValueError,
		match="unknown benchmark scenario",
	):
		run_smoke(
			tmp_path,
			iterations=1,
			scenarios=("missing",),
		)
