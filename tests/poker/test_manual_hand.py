import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from poker.game.actions import PlayerAction
from poker.game.game_state import GameState
from poker.player.player import Player
from tools.manual_hand import parse_action, prepare_next_hand


def test_parse_action_rejects_unknown_command_before_parsing_amount():
	with pytest.raises(ValueError, match="Unknown command"):
		parse_action("да ебашь так, чо")


def test_parse_action_requires_bet_amount():
	with pytest.raises(ValueError, match="Usage: bet N"):
		parse_action("bet")


def test_parse_action_requires_numeric_raise_amount():
	with pytest.raises(ValueError, match="positive integer"):
		parse_action("raise много")


def test_parse_action_accepts_all_in_alias():
	action, amount = parse_action("allin")

	assert action == PlayerAction.ALL_IN
	assert amount == 0


def test_prepare_next_hand_removes_busted_players_and_preserves_next_dealer():
	state = GameState()
	alice = Player("Alice", 205)
	bob = Player("Bob", 95)
	carol = Player("Carol", 0)
	state.add_player(alice)
	state.add_player(bob)
	state.add_player(carol)
	state.dealer_button_index = 0

	prepare_next_hand(state)

	assert state.players == [alice, bob]
	assert state.dealer_button_index == 0
	state.advance_dealer_button()
	assert state.players[state.dealer_button_index] is bob


def test_prepare_next_hand_rejects_table_with_one_funded_player():
	state = GameState()
	state.add_player(Player("Alice", 200))
	state.add_player(Player("Bob", 0))

	with pytest.raises(ValueError, match="Not enough players"):
		prepare_next_hand(state)

from tools.manual_scenarios import create_scenario, get_scenario, parse_card, scenario_names


def test_scenario_catalog_contains_core_debug_cases():
	assert {
		"default",
		"headsup",
		"minraise",
		"short-allin",
		"short-bb",
		"cumulative-reopen",
		"sidepot",
		"splitpot",
		"cascade",
		"sidepot-fold",
		"sidepot-split",
		"oddchip",
	} <= set(scenario_names())


def test_sidepot_scenario_has_unequal_stacks_and_fixed_cards():
	state, controller, scenario = create_scenario("sidepot")

	assert [player.chips + player.current_bet for player in state.players] == [20, 50, 100]
	assert [str(card) for card in state.players[0].hand.cards] == ["A♥", "A♦"]
	assert [str(card) for card in state.players[1].hand.cards] == ["K♥", "K♦"]
	assert [str(card) for card in state.players[2].hand.cards] == ["Q♥", "Q♦"]
	assert state.players[state.dealer_button_index].name == "Alice"
	assert controller.position_name(state, state.dealer_button_index) == "BTN"
	assert scenario.board == ("2C", "5D", "8S", "JC", "3H")


def test_scripted_scenario_deals_fixed_board():
	state, controller, _ = create_scenario("headsup")

	controller.process_action(state, PlayerAction.CALL)
	controller.process_action(state, PlayerAction.CHECK)
	assert [str(card) for card in state.board.cards] == ["2♣", "7♦", "10♥"]

	controller.process_action(state, PlayerAction.CHECK)
	controller.process_action(state, PlayerAction.CHECK)
	assert [str(card) for card in state.board.cards] == ["2♣", "7♦", "10♥", "J♠"]


def test_splitpot_scenario_board_forces_board_play():
	_, _, scenario = create_scenario("splitpot")

	assert scenario.board == ("10H", "JH", "QH", "KH", "AH")


def test_parse_card_keeps_ten_as_numeric_rank():
	assert str(parse_card("10s")) == "10♠"


def test_unknown_scenario_has_helpful_error():
	with pytest.raises(ValueError, match="scenario list"):
		get_scenario("dragon")


def test_cascade_scenario_exposes_four_contribution_levels():
	state, _, scenario = create_scenario("cascade")

	assert [player.chips + player.current_bet for player in state.players] == [20, 40, 80, 160]
	assert scenario.board == ("2C", "5D", "8S", "9C", "3H")


def test_sidepot_split_uses_board_that_forces_tie():
	_, _, scenario = create_scenario("sidepot-split")

	assert scenario.board == ("10H", "JH", "QH", "KH", "AH")

def test_short_big_blind_scenario_keeps_full_preflop_target():
	state, controller, _ = create_scenario("short-bb")

	assert state.players[2].chips == 0
	assert state.players[2].current_bet == 1
	assert state.betting.current_bet == 2
	assert controller.current_player(state) is state.players[0]


def test_cumulative_reopen_scenario_has_expected_stack_geometry():
	state, controller, scenario = create_scenario("cumulative-reopen")

	assert [player.chips + player.current_bet for player in state.players] == [100, 18, 100, 100, 13]
	assert controller.current_player(state).name == "Dave"
	assert scenario.board == ("8S", "9S", "10S", "JC", "QH")

def test_cumulative_reopen_scenario_allows_original_raiser_to_raise_again():
	state, controller, _ = create_scenario("cumulative-reopen")

	controller.process_action(state, PlayerAction.RAISE, 10)
	controller.process_action(state, PlayerAction.ALL_IN)
	controller.process_action(state, PlayerAction.CALL)
	controller.process_action(state, PlayerAction.ALL_IN)
	controller.process_action(state, PlayerAction.CALL)

	assert controller.current_player(state).name == "Dave"
	controller.process_action(state, PlayerAction.RAISE, 26)

	assert state.betting.current_bet == 26
	assert controller.minimum_raise == 8

