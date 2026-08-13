from poker.api.hand_state import build_hand_state_view
from poker.game.actions import PlayerAction
from poker.game.dealer import Dealer
from poker.game.game_state import GameState
from poker.game.hand_controller import HandController
from poker.player.player import Player


def _state_with_players(count):
	state = GameState()
	for index in range(count):
		state.add_player(
			Player(
				f"player_{index}",
				100,
			)
		)
	return state


def test_hand_state_exposes_only_actions_already_taken():
	state = _state_with_players(4)
	controller = HandController(Dealer(seed=42))
	controller.start_hand(state)

	first = controller.current_player(state)
	controller.process_action(
		state,
		PlayerAction.CALL,
	)
	view = build_hand_state_view(
		state,
		controller,
	)

	assert len(view.action_history) == 1
	assert view.action_history[0].player == first.name
	assert view.action_history[0].action == "call"
	assert view.action_history[0].street == "preflop"


def test_hand_state_uses_canonical_multiway_positions():
	state = _state_with_players(6)
	controller = HandController(Dealer(seed=7))
	controller.start_hand(state)

	view = build_hand_state_view(
		state,
		controller,
	)
	positions = {
		player.position
		for player in view.players
	}

	assert positions == {
		"BTN",
		"SB",
		"BB",
		"UTG",
		"HJ",
		"CO",
	}
