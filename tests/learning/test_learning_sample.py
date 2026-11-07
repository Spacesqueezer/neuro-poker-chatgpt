from poker.api.hand_state import (
	ActionDecision,
	HandStateView,
	LegalActions,
	PublicPlayerView,
)
from poker.game.actions import PlayerAction
from poker.learning.observation import LearningObservationEncoder
from poker.learning.sample import LEARNING_SAMPLE_VERSION, LearningSampleBuilder


def _state():
	return HandStateView(
		street="preflop",
		acting_player="hero",
		hole_cards=("A♠", "A♥"),
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


def test_learning_sample_combines_observation_legality_and_target():
	state = _state()
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
	sample = LearningSampleBuilder().build(
		state,
		legal,
		ActionDecision(PlayerAction.RAISE, 6),
		profile_scope="global",
	)

	assert sample.version == LEARNING_SAMPLE_VERSION
	assert len(sample.observation) == LearningObservationEncoder().size
	assert sample.action_mask == (1.0, 0.0, 1.0, 0.0, 1.0, 1.0)
	assert sample.action_index == 4
	assert sample.action_amount == 0.03
	assert sample.acting_player == "hero"
	assert sample.opponent_order == ("villain",)

	payload = sample.to_dict()
	assert payload["version"] == 1
	assert payload["action_index"] == 4
	assert payload["opponent_order"] == ["villain"]


def test_learning_sample_rejects_target_outside_legal_raise_bounds():
	state = _state()
	legal = LegalActions(
		actions=(PlayerAction.RAISE, PlayerAction.ALL_IN),
		min_raise_to=4,
		max_raise_to=100,
	)

	try:
		LearningSampleBuilder().build(
			state,
			legal,
			ActionDecision(PlayerAction.RAISE, 3),
			profile_scope="global",
		)
	except ValueError as error:
		assert "Decision is not legal" in str(error)
	else:
		raise AssertionError("Expected target legality validation")
