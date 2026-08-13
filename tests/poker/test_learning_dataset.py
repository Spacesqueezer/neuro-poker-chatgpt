import json

from poker.api.hand_state import (
	ActionDecision,
	HandStateView,
	LegalActions,
	PublicPlayerView,
)
from poker.game.actions import PlayerAction
from poker.learning.dataset import (
	LearningDatasetAnalyzer,
	LearningDatasetCapture,
	LearningDatasetWriter,
)


def _state():
	return HandStateView(
		street="preflop",
		acting_player="hero",
		hole_cards=("A♠", "K♠"),
		board=(),
		pot=3,
		target_bet=2,
		minimum_raise=2,
		dealer="hero",
		small_blind="hero",
		big_blind="villain",
		players=(
			PublicPlayerView(
				name="hero",
				chips=99,
				current_bet=1,
				total_contribution=1,
				folded=False,
				position="BTN",
			),
			PublicPlayerView(
				name="villain",
				chips=98,
				current_bet=2,
				total_contribution=2,
				folded=False,
				position="BB",
			),
		),
	)


def test_capture_writes_versioned_jsonl_and_analyzer_summarizes(tmp_path):
	path = tmp_path / "dataset.jsonl"
	capture = LearningDatasetCapture(
		LearningDatasetWriter(path),
		profile_scope="global",
	)
	legal = LegalActions(
		actions=(
			PlayerAction.FOLD,
			PlayerAction.CALL,
			PlayerAction.RAISE,
			PlayerAction.ALL_IN,
		),
		call_amount=1,
		min_raise_to=4,
		max_raise_to=100,
	)

	capture(
		_state(),
		legal,
		ActionDecision(PlayerAction.RAISE, 6),
	)
	capture(
		_state(),
		legal,
		ActionDecision(PlayerAction.CALL),
	)

	assert capture.samples_written == 2

	lines = path.read_text(encoding="utf-8").splitlines()
	assert len(lines) == 2
	assert json.loads(lines[0])["version"] == 1

	summary = LearningDatasetAnalyzer().analyze(path)

	assert summary["samples"] == 2
	assert summary["versions"] == {1: 2}
	assert summary["actions"] == {
		"call": 1,
		"raise": 1,
	}
	assert summary["acting_players"] == {"hero": 2}
	assert list(summary["observation_sizes"].values()) == [2]
	assert summary["action_mask_sizes"] == {6: 2}
	assert summary["action_sizing_sizes"] == {5: 2}


def test_analyzer_rejects_masked_target(tmp_path):
	path = tmp_path / "broken.jsonl"
	path.write_text(
		json.dumps(
			{
				"version": 1,
				"observation": [0.0],
				"action_mask": [1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
				"action_sizing": [0.0] * 5,
				"action_index": 4,
				"action_amount": 0.0,
				"acting_player": "hero",
				"opponent_order": [],
			}
		)
		+ "\n",
		encoding="utf-8",
	)

	try:
		LearningDatasetAnalyzer().analyze(path)
	except ValueError as error:
		assert "target action is masked illegal" in str(error)
	else:
		raise AssertionError("Expected dataset integrity validation")
