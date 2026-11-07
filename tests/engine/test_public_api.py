import pytest

from poker.api import ActionDecision, build_hand_state_view, get_legal_actions, play_hand
from poker.game.actions import PlayerAction
from poker.game.dealer import Dealer
from poker.game.game_state import GameState
from poker.game.hand_controller import HandController
from poker.player.player import Player


class CallingAgent:
	def choose_action(self, state, legal):
		if PlayerAction.CALL in legal.actions:
			return ActionDecision(PlayerAction.CALL)
		if PlayerAction.CHECK in legal.actions:
			return ActionDecision(PlayerAction.CHECK)
		return ActionDecision(PlayerAction.FOLD)


class BadAgent:
	def choose_action(self, state, legal):
		return ActionDecision(PlayerAction.RAISE, 1_000_000)


def create_started_hand(seed=42):
	state = GameState()
	for name in ("Alice", "Bob", "Carol"):
		state.add_player(Player(name, 100))
	controller = HandController(Dealer(seed=seed))
	controller.start_hand(state)
	return state, controller


def test_state_view_exposes_only_acting_players_hole_cards():
	state, controller = create_started_hand()
	view = build_hand_state_view(state, controller)

	assert view.acting_player == "Alice"
	assert len(view.hole_cards) == 2
	assert view.board == ()
	assert view.pot == 3
	assert view.target_bet == 2
	assert {player.name for player in view.players} == {"Alice", "Bob", "Carol"}
	assert not hasattr(view.players[0], "hole_cards")


def test_legal_actions_include_call_and_full_raise_range_preflop():
	state, controller = create_started_hand()
	legal = get_legal_actions(state, controller)

	assert PlayerAction.FOLD in legal.actions
	assert PlayerAction.CALL in legal.actions
	assert legal.call_amount == 2
	assert PlayerAction.RAISE in legal.actions
	assert legal.min_raise_to == 4
	assert legal.max_raise_to == 100
	assert legal.allows(PlayerAction.RAISE, 4)
	assert not legal.allows(PlayerAction.RAISE, 3)


def test_play_hand_returns_completed_reproducible_history():
	agents = {
		"Alice": CallingAgent(),
		"Bob": CallingAgent(),
		"Carol": CallingAgent(),
	}

	first = play_hand(agents, seed=4242)
	second = play_hand(agents, seed=4242)

	assert first.result == "showdown"
	assert second.result == "showdown"
	assert first.seed == second.seed == 4242
	assert [player["cards"] for player in first.players] == [
		player["cards"] for player in second.players
	]
	assert first.final_stacks == second.final_stacks
	assert sum(first.final_stacks.values()) == 300


def test_play_hand_can_select_dealer_for_position_rotation():
	agents = {
		"Alice": CallingAgent(),
		"Bob": CallingAgent(),
		"Carol": CallingAgent(),
	}

	history = play_hand(agents, seed=17, dealer_name="Carol")

	assert history.dealer == "Carol"
	assert sum(history.final_stacks.values()) == 300


def test_play_hand_rejects_agent_decision_outside_legal_range():
	agents = {
		"Alice": BadAgent(),
		"Bob": CallingAgent(),
		"Carol": CallingAgent(),
	}

	with pytest.raises(ValueError, match="Illegal agent decision"):
		play_hand(agents, seed=42)
