from poker.agents import CallingStationAgent, NitAgent
from poker.arena.runner import ArenaRunner
from poker.learning.dataset import (
	LearningDatasetAnalyzer,
	LearningDatasetCapture,
	LearningDatasetWriter,
)


def test_arena_captures_real_decisions_to_dataset(tmp_path):
	path = tmp_path / "arena.jsonl"
	capture = LearningDatasetCapture(
		LearningDatasetWriter(path),
		profile_scope="global",
	)
	runner = ArenaRunner(
		{
			"calling": CallingStationAgent(),
			"nit": NitAgent(),
		},
		starting_stack=100,
		decision_observer=capture,
	)

	stats = runner.run(
		hands=20,
		seed=42,
	)

	summary = LearningDatasetAnalyzer().analyze(path)

	assert stats.hands > 0
	assert capture.samples_written > 0
	assert summary["samples"] == capture.samples_written
	assert set(summary["acting_players"]) == {
		"calling",
		"nit",
	}
	assert summary["action_mask_sizes"] == {
		6: capture.samples_written,
	}
	assert summary["action_sizing_sizes"] == {
		5: capture.samples_written,
	}
