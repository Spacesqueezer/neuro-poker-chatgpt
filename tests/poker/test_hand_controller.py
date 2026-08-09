import pytest

from poker.game.actions import PlayerAction
from poker.game.dealer import Dealer
from poker.game.game_state import GameState
from poker.game.hand_controller import HandController
from poker.game.round_manager import GameStreet
from poker.player.player import Player


def make_state(player_count=2, chips=100):
	state = GameState()
	for index in range(player_count):
		state.add_player(Player(f"Player{index + 1}", chips))
	return state


def test_hand_controller_deals_first_cards():
	state = make_state()
	controller = HandController(Dealer())

	controller.start_hand(state)

	assert len(state.players[0].hand.cards) == 2
	assert len(state.players[1].hand.cards) == 2


def test_hand_controller_requires_two_players():
	state = make_state(player_count=1)
	controller = HandController(Dealer())

	with pytest.raises(ValueError, match="At least two players"):
		controller.start_hand(state)


def test_hand_controller_advances_to_flop():
	state = make_state()
	controller = HandController(Dealer())
	controller.start_hand(state)

	controller.advance_street(state)

	assert len(state.board.cards) == 3


def test_all_checks_complete_round_and_deal_flop():
	state = make_state()
	controller = HandController(Dealer())
	controller.start_hand(state)

	street = controller.process_action(state, PlayerAction.CHECK)
	assert street == GameStreet.PREFLOP
	assert controller.current_player(state) is state.players[1]

	street = controller.process_action(state, PlayerAction.CHECK)

	assert street == GameStreet.FLOP
	assert len(state.board.cards) == 3
	assert controller.current_player(state) is state.players[0]


def test_bet_and_call_move_chips_to_pot_and_deal_flop():
	state = make_state()
	controller = HandController(Dealer())
	controller.start_hand(state)

	controller.process_action(state, PlayerAction.BET, 10)
	street = controller.process_action(state, PlayerAction.CALL)

	assert street == GameStreet.FLOP
	assert state.betting.pot == 20
	assert state.betting.current_bet == 0
	assert state.players[0].chips == 90
	assert state.players[1].chips == 90
	assert state.players[0].current_bet == 0
	assert state.players[1].current_bet == 0


def test_raise_reopens_action_for_previous_player():
	state = make_state(player_count=3)
	controller = HandController(Dealer())
	controller.start_hand(state)

	controller.process_action(state, PlayerAction.BET, 10)
	controller.process_action(state, PlayerAction.CALL)
	controller.process_action(state, PlayerAction.RAISE, 20)

	assert controller.current_player(state) is state.players[0]
	assert not controller.betting_round.is_complete()

	controller.process_action(state, PlayerAction.CALL)
	assert controller.current_player(state) is state.players[1]
	assert not controller.betting_round.is_complete()

	street = controller.process_action(state, PlayerAction.CALL)

	assert street == GameStreet.FLOP
	assert state.betting.pot == 60


def test_check_is_rejected_when_player_faces_bet():
	state = make_state()
	controller = HandController(Dealer())
	controller.start_hand(state)
	controller.process_action(state, PlayerAction.BET, 10)

	with pytest.raises(ValueError, match="Cannot check"):
		controller.process_action(state, PlayerAction.CHECK)


def test_short_all_in_is_rejected_until_side_pots_exist():
	state = GameState()
	state.add_player(Player("Alice", 100))
	state.add_player(Player("Bob", 5))
	controller = HandController(Dealer())
	controller.start_hand(state)
	controller.process_action(state, PlayerAction.BET, 10)

	with pytest.raises(ValueError, match="side pot"):
		controller.process_action(state, PlayerAction.ALL_IN)
