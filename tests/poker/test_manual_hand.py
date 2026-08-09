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
