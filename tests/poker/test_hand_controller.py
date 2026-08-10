import pytest

from poker.cards.card import Card
from poker.enums import Rank, Suit
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


def test_short_all_in_call_is_allowed_below_current_target():
	state = GameState()
	state.add_player(Player("Alice", 100))
	state.add_player(Player("Bob", 5))
	state.add_player(Player("Carol", 100))
	controller = HandController(Dealer(), small_blind=1, big_blind=2)
	controller.start_hand(state)

	controller.process_action(state, PlayerAction.RAISE, 10)
	controller.process_action(state, PlayerAction.ALL_IN)

	assert state.players[1].chips == 0
	assert state.players[1].current_bet == 5
	assert state.players[1].total_contribution == 5
	assert state.betting.current_bet == 10

	street = controller.process_action(state, PlayerAction.CALL)

	assert street == GameStreet.FLOP
	assert state.betting.pot == 25


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

	assert street == GameStreet.COMPLETE
	assert state.players[1].chips == 102
	assert state.betting.pot == 0
	assert all(player.current_bet == 0 for player in state.players)


def test_postflop_bet_must_be_at_least_big_blind():
	state = make_state(player_count=3)
	controller = HandController(Dealer(), small_blind=1, big_blind=2)
	controller.start_hand(state)

	controller.process_action(state, PlayerAction.CALL)
	controller.process_action(state, PlayerAction.CALL)
	controller.process_action(state, PlayerAction.CHECK)

	with pytest.raises(ValueError, match="Minimum bet is 2"):
		controller.process_action(state, PlayerAction.BET, 1)


def test_raise_must_match_last_full_raise_size():
	state = make_state(player_count=3)
	controller = HandController(Dealer(), small_blind=1, big_blind=2)
	controller.start_hand(state)

	controller.process_action(state, PlayerAction.CALL)
	controller.process_action(state, PlayerAction.CALL)
	controller.process_action(state, PlayerAction.CHECK)

	controller.process_action(state, PlayerAction.CHECK)
	controller.process_action(state, PlayerAction.BET, 10)

	with pytest.raises(ValueError, match="Minimum raise target is 20"):
		controller.process_action(state, PlayerAction.RAISE, 12)

	controller.process_action(state, PlayerAction.RAISE, 20)
	assert state.betting.current_bet == 20
	assert controller.minimum_raise == 10


def test_full_raise_updates_next_minimum_raise_increment():
	state = make_state(player_count=3)
	controller = HandController(Dealer(), small_blind=1, big_blind=2)
	controller.start_hand(state)

	controller.process_action(state, PlayerAction.RAISE, 6)
	assert controller.minimum_raise == 4

	controller.process_action(state, PlayerAction.RAISE, 10)
	assert controller.minimum_raise == 4

	with pytest.raises(ValueError, match="Minimum raise target is 14"):
		controller.process_action(state, PlayerAction.RAISE, 12)


def test_short_all_in_raise_does_not_reopen_action_for_previous_player():
	state = GameState()
	state.add_player(Player("Alice", 100))
	state.add_player(Player("Bob", 15))
	state.add_player(Player("Carol", 100))
	controller = HandController(Dealer(), small_blind=1, big_blind=2)
	controller.start_hand(state)

	controller.process_action(state, PlayerAction.RAISE, 10)
	controller.process_action(state, PlayerAction.ALL_IN)

	assert state.betting.current_bet == 15
	assert controller.minimum_raise == 8

	controller.process_action(state, PlayerAction.CALL)

	with pytest.raises(ValueError, match="not reopened"):
		controller.process_action(state, PlayerAction.RAISE, 23)

	street = controller.process_action(state, PlayerAction.CALL)
	assert street == GameStreet.FLOP
	assert state.betting.pot == 45


def test_uncontested_hand_ends_as_complete_not_showdown():
	state = make_state(player_count=3)
	controller = HandController(Dealer(), small_blind=1, big_blind=2)
	controller.start_hand(state)

	controller.process_action(state, PlayerAction.FOLD)
	controller.process_action(state, PlayerAction.RAISE, 10)
	street = controller.process_action(state, PlayerAction.FOLD)

	assert street == GameStreet.COMPLETE
	assert state.round_manager.street == GameStreet.COMPLETE


def test_total_pot_includes_uncollected_current_bets():
	state = make_state(player_count=3)
	controller = HandController(Dealer(), small_blind=1, big_blind=2)
	controller.start_hand(state)

	assert state.betting.pot == 0
	assert controller.total_pot(state) == 3

	controller.process_action(state, PlayerAction.CALL)
	assert controller.total_pot(state) == 5


def test_all_in_call_runs_remaining_board_directly_to_showdown():
	state = make_state(player_count=3)
	controller = HandController(Dealer(), small_blind=1, big_blind=2)
	controller.start_hand(state)

	controller.process_action(state, PlayerAction.CALL)
	controller.process_action(state, PlayerAction.CALL)
	controller.process_action(state, PlayerAction.CHECK)

	controller.process_action(state, PlayerAction.CHECK)
	controller.process_action(state, PlayerAction.BET, 10)
	controller.process_action(state, PlayerAction.RAISE, 20)
	controller.process_action(state, PlayerAction.FOLD)
	controller.process_action(state, PlayerAction.ALL_IN)
	street = controller.process_action(state, PlayerAction.CALL)

	assert street == GameStreet.SHOWDOWN
	assert state.round_manager.street == GameStreet.SHOWDOWN
	assert len(state.board.cards) == 5
	assert state.betting.current_bet == 0
	assert state.betting.pot == 0
	assert controller.showdown_winners
	assert sum(player.chips for player in state.players) == 300
	assert all(player.current_bet == 0 for player in state.players)


def test_one_funded_player_and_one_all_in_player_also_runs_out():
	state = GameState()
	state.add_player(Player("Alice", 100))
	state.add_player(Player("Bob", 20))
	controller = HandController(Dealer(), small_blind=1, big_blind=2)
	controller.start_hand(state)

	controller.process_action(state, PlayerAction.RAISE, 20)
	street = controller.process_action(state, PlayerAction.CALL)

	assert street == GameStreet.SHOWDOWN
	assert len(state.board.cards) == 5
	assert state.betting.pot == 0
	assert controller.showdown_winners
	assert sum(player.chips for player in state.players) == 120


def test_showdown_pays_best_hand_and_clears_pot():
	state = GameState()
	alice = Player("Alice", 0)
	carol = Player("Carol", 0)
	state.add_player(alice)
	state.add_player(carol)
	state.dealer_button_index = 0
	alice.hand.add_card(Card(Rank.THREE, Suit.SPADES))
	alice.hand.add_card(Card(Rank.TEN, Suit.SPADES))
	carol.hand.add_card(Card(Rank.THREE, Suit.CLUBS))
	carol.hand.add_card(Card(Rank.FOUR, Suit.DIAMONDS))
	state.board.cards = [
		Card(Rank.TEN, Suit.CLUBS),
		Card(Rank.EIGHT, Suit.CLUBS),
		Card(Rank.TEN, Suit.HEARTS),
		Card(Rank.KING, Suit.HEARTS),
		Card(Rank.FOUR, Suit.CLUBS),
	]
	state.betting.pot = 205
	controller = HandController(Dealer())

	controller._resolve_showdown(state)

	assert controller.showdown_winners == [alice]
	assert controller.showdown_payouts[alice] == 205
	assert alice.chips == 205
	assert carol.chips == 0
	assert state.betting.pot == 0


def test_showdown_splits_tied_pot_and_awards_odd_chip_left_of_dealer():
	state = GameState()
	alice = Player("Alice", 0)
	bob = Player("Bob", 0)
	carol = Player("Carol", 0)
	for player in (alice, bob, carol):
		state.add_player(player)
	state.dealer_button_index = 0

	alice.hand.cards = [Card(Rank.TWO, Suit.CLUBS), Card(Rank.THREE, Suit.DIAMONDS)]
	bob.hand.cards = [Card(Rank.FOUR, Suit.CLUBS), Card(Rank.FIVE, Suit.DIAMONDS)]
	carol.hand.cards = [Card(Rank.SIX, Suit.CLUBS), Card(Rank.SEVEN, Suit.DIAMONDS)]
	state.board.cards = [
		Card(Rank.TEN, Suit.SPADES),
		Card(Rank.JACK, Suit.SPADES),
		Card(Rank.QUEEN, Suit.SPADES),
		Card(Rank.KING, Suit.SPADES),
		Card(Rank.ACE, Suit.SPADES),
	]
	state.betting.pot = 101
	controller = HandController(Dealer())

	controller._resolve_showdown(state)

	assert controller.showdown_winners == [bob, carol, alice]
	assert controller.showdown_payouts[bob] == 34
	assert controller.showdown_payouts[carol] == 34
	assert controller.showdown_payouts[alice] == 33
	assert state.betting.pot == 0


def test_three_level_all_in_builds_main_side_and_unmatched_refund():
	state = GameState()
	alice = Player("Alice", 0)
	bob = Player("Bob", 0)
	carol = Player("Carol", 0)
	for player in (alice, bob, carol):
		state.add_player(player)
	state.dealer_button_index = 0

	alice.hand.cards = [Card(Rank.ACE, Suit.HEARTS), Card(Rank.ACE, Suit.DIAMONDS)]
	bob.hand.cards = [Card(Rank.KING, Suit.HEARTS), Card(Rank.KING, Suit.DIAMONDS)]
	carol.hand.cards = [Card(Rank.QUEEN, Suit.HEARTS), Card(Rank.QUEEN, Suit.DIAMONDS)]
	state.board.cards = [
		Card(Rank.TWO, Suit.CLUBS),
		Card(Rank.FIVE, Suit.DIAMONDS),
		Card(Rank.EIGHT, Suit.SPADES),
		Card(Rank.JACK, Suit.CLUBS),
		Card(Rank.THREE, Suit.HEARTS),
	]
	alice.total_contribution = 20
	bob.total_contribution = 50
	carol.total_contribution = 100
	state.betting.pot = 170
	controller = HandController(Dealer())

	controller._resolve_showdown(state)

	assert alice.chips == 60
	assert bob.chips == 60
	assert carol.chips == 50
	assert controller.showdown_payouts[alice] == 60
	assert controller.showdown_payouts[bob] == 60
	assert controller.showdown_payouts[carol] == 50
	assert controller.showdown_refunds == {carol: 50}
	assert controller.showdown_winners == [alice, bob]
	assert state.betting.pot == 0
	assert sum(player.chips for player in state.players) == 170


def test_call_with_too_few_chips_becomes_short_all_in_call():
	state = GameState()
	state.add_player(Player("Alice", 100))
	state.add_player(Player("Bob", 5))
	state.add_player(Player("Carol", 100))
	controller = HandController(Dealer(), small_blind=1, big_blind=2)
	controller.start_hand(state)

	controller.process_action(state, PlayerAction.RAISE, 10)
	controller.process_action(state, PlayerAction.CALL)

	bob = state.players[1]
	assert bob.chips == 0
	assert bob.current_bet == 5
	assert bob.total_contribution == 5
	assert state.betting.current_bet == 10


def test_player_contribution_accumulates_across_streets():
	state = make_state(player_count=3)
	controller = HandController(Dealer(), small_blind=1, big_blind=2)
	controller.start_hand(state)

	controller.process_action(state, PlayerAction.CALL)
	controller.process_action(state, PlayerAction.CALL)
	controller.process_action(state, PlayerAction.CHECK)

	assert [player.total_contribution for player in state.players] == [2, 2, 2]

	controller.process_action(state, PlayerAction.BET, 10)
	controller.process_action(state, PlayerAction.CALL)
	controller.process_action(state, PlayerAction.CALL)

	assert [player.total_contribution for player in state.players] == [12, 12, 12]


def test_pot_layers_are_derived_from_contribution_levels():
	state = GameState()
	alice = Player("Alice", 0)
	bob = Player("Bob", 0)
	carol = Player("Carol", 0)
	for player in (alice, bob, carol):
		state.add_player(player)
	alice.total_contribution = 20
	bob.total_contribution = 50
	carol.total_contribution = 100
	controller = HandController(Dealer())

	layers = controller._build_pot_layers(state)

	assert [(amount, [player.name for player in eligible]) for amount, eligible in layers] == [
		(60, ["Alice", "Bob", "Carol"]),
		(60, ["Bob", "Carol"]),
		(50, ["Carol"]),
	]


def test_hand_history_records_blinds_actions_and_uncontested_result():
	state = make_state(player_count=3)
	controller = HandController(Dealer(), small_blind=1, big_blind=2)
	controller.start_hand(state)

	controller.process_action(state, PlayerAction.FOLD)
	controller.process_action(state, PlayerAction.RAISE, 10)
	controller.process_action(state, PlayerAction.FOLD)

	history = controller.hand_history
	assert history is not None
	assert history.dealer == "Player1"
	assert history.events[0].type == "blinds"
	actions = [event for event in history.events if event.type == "action"]
	assert [event.data["action"] for event in actions] == ["fold", "raise", "fold"]
	assert history.result == "complete"
	assert history.final_stacks["Player2"] == 102


def test_hand_history_records_streets_and_showdown():
	state = make_state(player_count=2)
	controller = HandController(Dealer())
	controller.start_hand(state)

	controller.process_action(state, PlayerAction.CALL)
	controller.process_action(state, PlayerAction.CHECK)
	controller.process_action(state, PlayerAction.CHECK)
	controller.process_action(state, PlayerAction.CHECK)
	controller.process_action(state, PlayerAction.CHECK)
	controller.process_action(state, PlayerAction.CHECK)
	controller.process_action(state, PlayerAction.CHECK)
	controller.process_action(state, PlayerAction.CHECK)

	history = controller.hand_history
	streets = [event.data["street"] for event in history.events if event.type == "street"]
	assert streets == ["flop", "turn", "river"]
	assert history.events[-1].type == "showdown"
	assert history.result == "showdown"
