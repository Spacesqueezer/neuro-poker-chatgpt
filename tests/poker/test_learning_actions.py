from poker.api.hand_state import HandStateView, LegalActions, PublicPlayerView
from poker.game.actions import PlayerAction
from poker.learning.actions import LearningActionEncoder


def _state():
	return HandStateView(
		street="flop",
		acting_player="hero",
		hole_cards=("A♠", "K♠"),
		board=("2♣", "7♦", "J♥"),
		pot=20,
		target_bet=10,
		minimum_raise=10,
		dealer="villain",
		small_blind="hero",
		big_blind="villain",
		players=(
			PublicPlayerView(
				name="hero",
				chips=80,
				current_bet=5,
				total_contribution=20,
				folded=False,
				position="BB",
			),
			PublicPlayerView(
				name="villain",
				chips=70,
				current_bet=10,
				total_contribution=30,
				folded=False,
				position="BTN",
			),
		),
	)


def test_action_encoder_has_stable_mask_order_and_normalized_sizing():
	legal = LegalActions(
		actions=(
			PlayerAction.FOLD,
			PlayerAction.CALL,
			PlayerAction.RAISE,
			PlayerAction.ALL_IN,
		),
		call_amount=5,
		min_raise_to=20,
		max_raise_to=85,
	)
	encoded = LearningActionEncoder().encode(legal, _state())

	assert encoded.action_names == (
		"fold",
		"check",
		"call",
		"bet",
		"raise",
		"all_in",
	)
	assert encoded.mask == (1.0, 0.0, 1.0, 0.0, 1.0, 1.0)
	assert encoded.sizing == (
		0.025,
		0.0,
		0.0,
		0.1,
		0.425,
	)
	assert encoded.allows(PlayerAction.RAISE) is True
	assert encoded.allows(PlayerAction.CHECK) is False


def test_action_target_rejects_illegal_decision():
	legal = LegalActions(
		actions=(PlayerAction.CHECK, PlayerAction.ALL_IN),
	)

	try:
		LearningActionEncoder().target(
			type("Decision", (), {
				"action": PlayerAction.RAISE,
				"amount": 20,
			})(),
			legal,
			_state(),
		)
	except ValueError as error:
		assert "Decision is not legal" in str(error)
	else:
		raise AssertionError("Expected illegal decision validation")
