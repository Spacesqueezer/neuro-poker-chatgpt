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


def test_hand_controller_deals_first_cards_and_posts_heads_up_blinds():
	state = make_state()
	controller = HandController(Dealer(), small_blind=1, big_blind=2)

	controller.start_hand(state)

	assert len(state.players[0].hand.cards) == 2
	assert len(state.players[1].hand.cards) == 2
	assert state.dealer_button_index == 0
	assert controller.small_blind_index == 0
	assert controller.big_blind_index == 1
	assert state.players[0].current_bet == 1
	assert state.players[1].current_bet == 2
	assert state.players[0].chips == 99
	assert state.players[1].chips == 98
	assert state.betting.current_bet == 2
	assert controller.current_player(state) is state.players[0]


def test_hand_controller_requires_two_players():
	state = make_state(player_count=1)
	controller = HandController(Dealer())

	with pytest.raises(ValueError, match="At least two players"):
		controller.start_hand(state)


def test_hand_controller_assigns_three_player_positions_and_utg_action():
	state = make_state(player_count=3)
	controller = HandController(Dealer(), small_blind=1, big_blind=2)

	controller.start_hand(state)

	assert state.dealer_button_index == 0
	assert controller.small_blind_index == 1
	assert controller.big_blind_index == 2
	assert controller.current_player(state) is state.players[0]
	assert state.players[1].current_bet == 1
	assert state.players[2].current_bet == 2


def test_dealer_button_rotates_between_hands():
	state = make_state(player_count=3)
	controller = HandController(Dealer())

	controller.start_hand(state)
	assert state.dealer_button_index == 0
	assert controller.small_blind_index == 1
	assert controller.big_blind_index == 2

	controller.start_hand(state)
	assert state.dealer_button_index == 1
	assert controller.small_blind_index == 2
	assert controller.big_blind_index == 0


def test_preflop_calls_collect_blinds_and_deal_flop():
	state = make_state(player_count=3)
	controller = HandController(Dealer(), small_blind=1, big_blind=2)
	controller.start_hand(state)

	controller.process_action(state, PlayerAction.CALL)
	controller.process_action(state, PlayerAction.CALL)
	street = controller.process_action(state, PlayerAction.CHECK)

	assert street == GameStreet.FLOP
	assert len(state.board.cards) == 3
	assert state.betting.pot == 6
	assert state.betting.current_bet == 0
	assert all(player.current_bet == 0 for player in state.players)
	assert controller.current_player(state) is state.players[1]


def test_postflop_action_starts_left_of_dealer():
	state = make_state(player_count=3)
	controller = HandController(Dealer())
	controller.start_hand(state)

	controller.process_action(state, PlayerAction.CALL)
	controller.process_action(state, PlayerAction.CALL)
	controller.process_action(state, PlayerAction.CHECK)

	assert state.round_manager.street == GameStreet.FLOP
	assert controller.current_player(state) is state.players[1]


def test_heads_up_postflop_action_starts_with_big_blind():
	state = make_state(player_count=2)
	controller = HandController(Dealer())
	controller.start_hand(state)

	controller.process_action(state, PlayerAction.CALL)
	controller.process_action(state, PlayerAction.CHECK)

	assert state.round_manager.street == GameStreet.FLOP
	assert controller.current_player(state) is state.players[1]


def test_raise_reopens_action_for_previous_players_preflop():
	state = make_state(player_count=3)
	controller = HandController(Dealer())
	controller.start_hand(state)

	controller.process_action(state, PlayerAction.RAISE, 6)
	controller.process_action(state, PlayerAction.CALL)
	controller.process_action(state, PlayerAction.CALL)

	assert state.round_manager.street == GameStreet.FLOP
	assert state.betting.pot == 18


def test_check_is_rejected_when_player_faces_big_blind():
	state = make_state(player_count=3)
	controller = HandController(Dealer())
	controller.start_hand(state)

	with pytest.raises(ValueError, match="Cannot check"):
		controller.process_action(state, PlayerAction.CHECK)


def test_short_all_in_is_rejected_until_side_pots_exist():
	state = GameState()
	state.add_player(Player("Alice", 100))
	state.add_player(Player("Bob", 5))
	state.add_player(Player("Carol", 100))
	controller = HandController(Dealer(), small_blind=1, big_blind=2)
	controller.start_hand(state)

	controller.process_action(state, PlayerAction.RAISE, 10)

	with pytest.raises(ValueError, match="side pot"):
		controller.process_action(state, PlayerAction.ALL_IN)


def test_blind_configuration_is_validated():
	with pytest.raises(ValueError, match="Small blind"):
		HandController(Dealer(), small_blind=0, big_blind=2)

	with pytest.raises(ValueError, match="Big blind"):
		HandController(Dealer(), small_blind=2, big_blind=2)


def test_last_active_player_wins_uncontested_pot():
	state = make_state(player_count=3)
	controller = HandController(Dealer(), small_blind=1, big_blind=2)
	controller.start_hand(state)

	controller.process_action(state, PlayerAction.FOLD)
	controller.process_action(state, PlayerAction.RAISE, 10)
	street = controller.process_action(state, PlayerAction.FOLD)

	assert street == GameStreet.SHOWDOWN
	assert state.players[1].chips == 102
	assert state.betting.pot == 0
	assert all(player.current_bet == 0 for player in state.players)
