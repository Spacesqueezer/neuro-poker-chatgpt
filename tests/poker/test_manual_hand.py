import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from poker.game.actions import PlayerAction
from tools.manual_hand import parse_action


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
