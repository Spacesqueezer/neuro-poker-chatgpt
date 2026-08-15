import pytest

from poker.cards.card import Card
from poker.enums import Rank, Suit
from poker.solver import (
	CFRTrainer,
	HeadsUpHoldemDeal,
	HoldemActionAbstraction,
	RestrictedHeadsUpHoldemGame,
)


def card(rank, suit):
	return Card(rank=rank, suit=suit)


def board():
	return (
		card(Rank.TWO, Suit.CLUBS),
		card(Rank.SEVEN, Suit.DIAMONDS),
		card(Rank.NINE, Suit.HEARTS),
		card(Rank.JACK, Suit.SPADES),
		card(Rank.THREE, Suit.CLUBS),
	)


def deal(hero, villain, weight=1.0):
	return HeadsUpHoldemDeal(
		hole_cards=(hero, villain),
		board=board(),
		weight=weight,
	)


def check_down(game, state):
	while not game.is_terminal_node(state):
		assert "check" in game.legal_actions(state)
		state = game.next_node(state, "check")
	return state


def test_restricted_holdem_normalizes_explicit_deal_weights():
	first = deal(
		(
			card(Rank.ACE, Suit.SPADES),
			card(Rank.ACE, Suit.HEARTS),
		),
		(
			card(Rank.KING, Suit.SPADES),
			card(Rank.KING, Suit.HEARTS),
		),
		weight=1.0,
	)
	second = deal(
		(
			card(Rank.QUEEN, Suit.SPADES),
			card(Rank.QUEEN, Suit.HEARTS),
		),
		(
			card(Rank.TEN, Suit.SPADES),
			card(Rank.TEN, Suit.HEARTS),
		),
		weight=3.0,
	)

	nodes = RestrictedHeadsUpHoldemGame(
		(first, second)
	).initial_nodes()

	assert [node.probability for node in nodes] == [
		0.25,
		0.75,
	]


def test_restricted_holdem_information_set_hides_opponent_cards():
	hero = (
		card(Rank.ACE, Suit.SPADES),
		card(Rank.ACE, Suit.HEARTS),
	)
	first = deal(
		hero,
		(
			card(Rank.KING, Suit.SPADES),
			card(Rank.KING, Suit.HEARTS),
		),
	)
	second = deal(
		tuple(reversed(hero)),
		(
			card(Rank.QUEEN, Suit.SPADES),
			card(Rank.QUEEN, Suit.HEARTS),
		),
	)
	game = RestrictedHeadsUpHoldemGame(
		(first, second)
	)
	nodes = game.initial_nodes()

	assert (
		game.information_set_for_node(
			nodes[0].state,
			player=0,
		)
		== game.information_set_for_node(
			nodes[1].state,
			player=0,
		)
	)


def test_restricted_holdem_preflop_information_set_hides_future_board():
	hero = (
		card(Rank.ACE, Suit.SPADES),
		card(Rank.ACE, Suit.HEARTS),
	)
	villain = (
		card(Rank.KING, Suit.SPADES),
		card(Rank.KING, Suit.HEARTS),
	)
	first = deal(hero, villain)
	second = HeadsUpHoldemDeal(
		hole_cards=(hero, villain),
		board=(
			card(Rank.FOUR, Suit.CLUBS),
			card(Rank.FIVE, Suit.DIAMONDS),
			card(Rank.SIX, Suit.HEARTS),
			card(Rank.EIGHT, Suit.SPADES),
			card(Rank.TEN, Suit.CLUBS),
		),
	)
	game = RestrictedHeadsUpHoldemGame(
		(first, second)
	)
	nodes = game.initial_nodes()

	first_info = game.information_set_for_node(
		nodes[0].state,
		player=0,
	)
	second_info = game.information_set_for_node(
		nodes[1].state,
		player=0,
	)

	assert first_info == second_info
	assert first_info[2] == "preflop"
	assert first_info[3] == ()


def test_restricted_holdem_terminal_utilities_are_zero_sum():
	game = RestrictedHeadsUpHoldemGame((
		deal(
			(
				card(Rank.ACE, Suit.SPADES),
				card(Rank.ACE, Suit.HEARTS),
			),
			(
				card(Rank.KING, Suit.SPADES),
				card(Rank.KING, Suit.HEARTS),
			),
		),
	))
	root = game.initial_nodes()[0].state

	fold = game.next_node(root, "fold")
	call = check_down(
		game,
		game.next_node(root, "call"),
	)
	raise_call = check_down(
		game,
		game.next_node(
			game.next_node(root, "raise"),
			"call",
		),
	)
	shove_fold = game.next_node(
		game.next_node(root, "all_in"),
		"fold",
	)
	showdown = game.next_node(
		game.next_node(root, "all_in"),
		"call",
	)

	for state in (
		fold,
		call,
		raise_call,
		shove_fold,
		showdown,
	):
		assert (
			game.terminal_node_utility(state, player=0)
			== -game.terminal_node_utility(state, player=1)
		)

	assert game.terminal_node_utility(call, player=0) == 2.0
	assert (
		game.terminal_node_utility(
			raise_call,
			player=0,
		)
		== 6.0
	)
	assert game.terminal_node_utility(showdown, player=0) == 20.0


def test_restricted_holdem_exposes_small_preflop_action_abstraction():
	game = RestrictedHeadsUpHoldemGame((
		deal(
			(
				card(Rank.ACE, Suit.SPADES),
				card(Rank.ACE, Suit.HEARTS),
			),
			(
				card(Rank.KING, Suit.SPADES),
				card(Rank.KING, Suit.HEARTS),
			),
		),
	))
	root = game.initial_nodes()[0].state

	assert game.legal_actions(root) == (
		"fold",
		"call",
		"raise",
		"all_in",
	)
	assert game.legal_actions(
		game.next_node(root, "raise")
	) == (
		"fold",
		"call",
		"all_in",
	)
	flop = game.next_node(root, "call")
	assert not game.is_terminal_node(flop)
	assert flop.street == "flop"
	assert flop.public_board == board()[:3]


def test_restricted_holdem_progresses_public_streets_by_checking_down():
	game = RestrictedHeadsUpHoldemGame((
		deal(
			(
				card(Rank.ACE, Suit.SPADES),
				card(Rank.ACE, Suit.HEARTS),
			),
			(
				card(Rank.KING, Suit.SPADES),
				card(Rank.KING, Suit.HEARTS),
			),
		),
	))
	root = game.initial_nodes()[0].state

	flop = game.next_node(root, "call")
	assert flop.street == "flop"
	assert flop.public_board == board()[:3]
	assert game.player_to_act(flop) == 1

	flop_second = game.next_node(flop, "check")
	assert flop_second.street == "flop"
	assert game.player_to_act(flop_second) == 0

	turn = game.next_node(flop_second, "check")
	assert turn.street == "turn"
	assert turn.public_board == board()[:4]

	turn_second = game.next_node(turn, "check")
	river = game.next_node(turn_second, "check")
	assert river.street == "river"
	assert river.public_board == board()

	river_second = game.next_node(river, "check")
	showdown = game.next_node(river_second, "check")
	assert game.is_terminal_node(showdown)


def test_restricted_holdem_tracks_player_commitments_explicitly():
	game = RestrictedHeadsUpHoldemGame((
		deal(
			(
				card(Rank.ACE, Suit.SPADES),
				card(Rank.ACE, Suit.HEARTS),
			),
			(
				card(Rank.KING, Suit.SPADES),
				card(Rank.KING, Suit.HEARTS),
			),
		),
	))
	root = game.initial_nodes()[0].state

	assert root.commitments == (1, 2)
	assert root.street_commitments == (1, 2)
	assert root.collected_pot == 0
	assert root.target_bet == 2

	raised = game.next_node(root, "raise")
	assert raised.commitments == (6, 2)
	assert raised.street_commitments == (6, 2)

	flop = game.next_node(raised, "call")
	assert flop.commitments == (6, 6)
	assert flop.street_commitments == (0, 0)
	assert flop.collected_pot == 12
	assert flop.target_bet == 0

	bet = game.next_node(flop, "bet_2bb")
	assert bet.commitments == (6, 10)
	assert bet.street_commitments == (0, 4)
	assert bet.collected_pot == 12
	assert bet.target_bet == 4

	turn = game.next_node(bet, "call")
	assert turn.commitments == (10, 10)
	assert turn.street_commitments == (0, 0)
	assert turn.collected_pot == 20
	assert turn.matched_stake == 10


def test_restricted_holdem_postflop_bet_call_tracks_matched_stake():
	game = RestrictedHeadsUpHoldemGame((
		deal(
			(
				card(Rank.ACE, Suit.SPADES),
				card(Rank.ACE, Suit.HEARTS),
			),
			(
				card(Rank.KING, Suit.SPADES),
				card(Rank.KING, Suit.HEARTS),
			),
		),
	))
	root = game.initial_nodes()[0].state
	flop = game.next_node(root, "call")

	assert flop.matched_stake == 2
	assert game.legal_actions(flop) == (
		"check",
		"bet_1bb",
		"bet_2bb",
	)

	bet = game.next_node(flop, "bet_1bb")
	assert game.legal_actions(bet) == (
		"fold",
		"call",
		"raise",
	)

	turn = game.next_node(bet, "call")
	assert turn.street == "turn"
	assert turn.matched_stake == 4

	showdown = check_down(game, turn)
	assert game.terminal_node_utility(
		showdown,
		player=0,
	) == 4.0


def test_restricted_holdem_allows_one_postflop_raise():
	game = RestrictedHeadsUpHoldemGame((
		deal(
			(
				card(Rank.ACE, Suit.SPADES),
				card(Rank.ACE, Suit.HEARTS),
			),
			(
				card(Rank.KING, Suit.SPADES),
				card(Rank.KING, Suit.HEARTS),
			),
		),
	))
	root = game.initial_nodes()[0].state
	flop = game.next_node(root, "call")
	bet = game.next_node(flop, "bet_1bb")
	raised = game.next_node(bet, "raise")

	assert raised.commitments == (6, 4)
	assert game.legal_actions(raised) == (
		"fold",
		"call",
	)

	turn = game.next_node(raised, "call")
	assert turn.street == "turn"
	assert turn.commitments == (6, 6)


def test_restricted_holdem_check_bet_raise_fold_refunds_unmatched_chips():
	game = RestrictedHeadsUpHoldemGame((
		deal(
			(
				card(Rank.ACE, Suit.SPADES),
				card(Rank.ACE, Suit.HEARTS),
			),
			(
				card(Rank.KING, Suit.SPADES),
				card(Rank.KING, Suit.HEARTS),
			),
		),
	))
	root = game.initial_nodes()[0].state
	flop = game.next_node(root, "call")
	checked = game.next_node(flop, "check")
	bet = game.next_node(checked, "bet_1bb")
	raised = game.next_node(bet, "raise")
	fold = game.next_node(raised, "fold")

	assert raised.commitments == (4, 6)
	assert game.is_terminal_node(fold)
	assert game.terminal_node_utility(
		fold,
		player=0,
	) == -4.0
	assert game.terminal_node_utility(
		fold,
		player=1,
	) == 4.0


def test_restricted_holdem_action_abstraction_configures_stakes():
	game = RestrictedHeadsUpHoldemGame(
		(
			deal(
				(
					card(Rank.ACE, Suit.SPADES),
					card(Rank.ACE, Suit.HEARTS),
				),
				(
					card(Rank.KING, Suit.SPADES),
					card(Rank.KING, Suit.HEARTS),
				),
			),
		),
		action_abstraction=HoldemActionAbstraction(
			preflop_raise_bb=4,
			postflop_bet_sizes_bb=(1, 2),
			postflop_raise_increment_multiplier=2,
		),
	)
	root = game.initial_nodes()[0].state
	raised = game.next_node(root, "raise")
	flop = game.next_node(raised, "call")

	assert flop.matched_stake == 8
	assert game.legal_actions(flop) == (
		"check",
		"bet_1bb",
		"bet_2bb",
	)

	small_bet = game.next_node(flop, "bet_1bb")
	small_turn = game.next_node(
		small_bet,
		"call",
	)
	assert small_turn.matched_stake == 10

	large_bet = game.next_node(flop, "bet_2bb")
	large_turn = game.next_node(
		large_bet,
		"call",
	)
	assert large_turn.matched_stake == 12

	raise_source = game.next_node(flop, "bet_1bb")
	raised = game.next_node(
		raise_source,
		"raise",
	)
	assert raised.commitments == (14, 10)


def test_restricted_holdem_supports_asymmetric_starting_stacks():
	game = RestrictedHeadsUpHoldemGame(
		(
			deal(
				(
					card(Rank.ACE, Suit.SPADES),
					card(Rank.ACE, Suit.HEARTS),
				),
				(
					card(Rank.KING, Suit.SPADES),
					card(Rank.KING, Suit.HEARTS),
				),
			),
		),
		starting_stacks=(8, 20),
	)
	root = game.initial_nodes()[0].state

	assert root.starting_stacks == (8, 20)
	assert root.commitments == (1, 2)
	assert game.information_set_for_node(root, 0)[-1] == (8, 20)

	raised = game.next_node(root, "raise")
	assert raised.commitments == (6, 2)

	showdown = game.next_node(raised, "all_in")
	assert game.is_terminal_node(showdown)
	assert showdown.commitments == (8, 20)
	assert showdown.matched_stake == 8
	assert game.terminal_node_utility(showdown, 0) == 8.0


def test_restricted_holdem_short_stack_call_is_capped():
	game = RestrictedHeadsUpHoldemGame(
		(
			deal(
				(
					card(Rank.ACE, Suit.SPADES),
					card(Rank.ACE, Suit.HEARTS),
				),
				(
					card(Rank.KING, Suit.SPADES),
					card(Rank.KING, Suit.HEARTS),
				),
			),
		),
		starting_stacks=(5, 20),
	)
	root = game.initial_nodes()[0].state
	flop = game.next_node(root, "call")
	bet = game.next_node(flop, "bet_2bb")
	showdown = game.next_node(bet, "call")

	assert game.is_terminal_node(showdown)
	assert showdown.showdown_runout
	assert showdown.street == "flop"
	assert showdown.commitments == (5, 6)
	assert showdown.matched_stake == 5
	assert game.terminal_node_utility(showdown, 0) == 5.0


def test_restricted_holdem_postflop_raise_respects_actor_stack_cap():
	game = RestrictedHeadsUpHoldemGame(
		(
			deal(
				(
					card(Rank.ACE, Suit.SPADES),
					card(Rank.ACE, Suit.HEARTS),
				),
				(
					card(Rank.KING, Suit.SPADES),
					card(Rank.KING, Suit.HEARTS),
				),
			),
		),
		starting_stacks=(7, 20),
	)
	root = game.initial_nodes()[0].state
	flop = game.next_node(root, "call")
	bet = game.next_node(flop, "bet_2bb")
	raised = game.next_node(bet, "raise")

	assert raised.commitments == (7, 6)

	showdown = game.next_node(raised, "call")
	assert game.is_terminal_node(showdown)
	assert showdown.showdown_runout
	assert showdown.commitments == (7, 7)
	assert showdown.matched_stake == 7


def test_restricted_holdem_prunes_actions_against_all_in_big_blind():
	game = RestrictedHeadsUpHoldemGame(
		(
			deal(
				(
					card(Rank.ACE, Suit.SPADES),
					card(Rank.ACE, Suit.HEARTS),
				),
				(
					card(Rank.KING, Suit.SPADES),
					card(Rank.KING, Suit.HEARTS),
				),
			),
		),
		starting_stacks=(20, 2),
	)
	root = game.initial_nodes()[0].state

	assert not game.is_terminal_node(root)
	assert game.legal_actions(root) == ("fold", "call")

	showdown = game.next_node(root, "call")
	assert game.is_terminal_node(showdown)
	assert showdown.showdown_runout
	assert showdown.commitments == (2, 2)


def test_restricted_holdem_small_blind_all_in_is_initial_runout():
	game = RestrictedHeadsUpHoldemGame(
		(
			deal(
				(
					card(Rank.ACE, Suit.SPADES),
					card(Rank.ACE, Suit.HEARTS),
				),
				(
					card(Rank.KING, Suit.SPADES),
					card(Rank.KING, Suit.HEARTS),
				),
			),
		),
		starting_stacks=(1, 20),
	)
	root = game.initial_nodes()[0].state

	assert game.is_terminal_node(root)
	assert root.showdown_runout
	assert root.matched_stake == 1
	assert game.terminal_node_utility(root, 0) == 1.0


def test_restricted_holdem_all_in_postflop_bet_removes_raise():
	game = RestrictedHeadsUpHoldemGame(
		(
			deal(
				(
					card(Rank.ACE, Suit.SPADES),
					card(Rank.ACE, Suit.HEARTS),
				),
				(
					card(Rank.KING, Suit.SPADES),
					card(Rank.KING, Suit.HEARTS),
				),
			),
		),
		starting_stacks=(20, 4),
	)
	root = game.initial_nodes()[0].state
	flop = game.next_node(root, "call")
	bet = game.next_node(flop, "bet_1bb")

	assert bet.commitments == (2, 4)
	assert game.legal_actions(bet) == ("fold", "call")

	showdown = game.next_node(bet, "call")
	assert game.is_terminal_node(showdown)
	assert showdown.showdown_runout
	assert showdown.commitments == (4, 4)


def test_restricted_holdem_rejects_invalid_asymmetric_stacks():
	base_deal = deal(
		(
			card(Rank.ACE, Suit.SPADES),
			card(Rank.ACE, Suit.HEARTS),
		),
		(
			card(Rank.KING, Suit.SPADES),
			card(Rank.KING, Suit.HEARTS),
		),
	)

	with pytest.raises(
		ValueError,
		match="exactly two stacks",
	):
		RestrictedHeadsUpHoldemGame(
			(base_deal,),
			starting_stacks=(20,),
		)

	with pytest.raises(
		ValueError,
		match="small blind",
	):
		RestrictedHeadsUpHoldemGame(
			(base_deal,),
			starting_stacks=(0, 20),
		)

	with pytest.raises(
		ValueError,
		match="big blind",
	):
		RestrictedHeadsUpHoldemGame(
			(base_deal,),
			starting_stacks=(20, 1),
		)


def test_restricted_holdem_rejects_invalid_action_abstraction():
	base_deal = deal(
		(
			card(Rank.ACE, Suit.SPADES),
			card(Rank.ACE, Suit.HEARTS),
		),
		(
			card(Rank.KING, Suit.SPADES),
			card(Rank.KING, Suit.HEARTS),
		),
	)

	with pytest.raises(
		ValueError,
		match="preflop_raise_bb",
	):
		RestrictedHeadsUpHoldemGame(
			(base_deal,),
			action_abstraction=HoldemActionAbstraction(
				preflop_raise_bb=1,
			),
		)

	with pytest.raises(
		ValueError,
		match="postflop_bet_sizes_bb",
	):
		RestrictedHeadsUpHoldemGame(
			(base_deal,),
			action_abstraction=HoldemActionAbstraction(
				postflop_bet_sizes_bb=(),
			),
		)

	with pytest.raises(
		ValueError,
		match="unique and increasing",
	):
		RestrictedHeadsUpHoldemGame(
			(base_deal,),
			action_abstraction=HoldemActionAbstraction(
				postflop_bet_sizes_bb=(2, 1),
			),
		)

	with pytest.raises(
		ValueError,
		match="postflop_raise_increment_multiplier",
	):
		RestrictedHeadsUpHoldemGame(
			(base_deal,),
			action_abstraction=HoldemActionAbstraction(
				postflop_raise_increment_multiplier=0,
			),
		)


def test_restricted_holdem_postflop_fold_awards_existing_matched_stake():
	game = RestrictedHeadsUpHoldemGame((
		deal(
			(
				card(Rank.ACE, Suit.SPADES),
				card(Rank.ACE, Suit.HEARTS),
			),
			(
				card(Rank.KING, Suit.SPADES),
				card(Rank.KING, Suit.HEARTS),
			),
		),
	))
	root = game.initial_nodes()[0].state
	flop = game.next_node(root, "call")
	bet = game.next_node(flop, "bet_1bb")
	fold = game.next_node(bet, "fold")

	assert game.is_terminal_node(fold)
	assert game.terminal_node_utility(fold, player=0) == -2.0
	assert game.terminal_node_utility(fold, player=1) == 2.0


def test_restricted_holdem_cfr_uses_generic_solver_boundary():
	game = RestrictedHeadsUpHoldemGame((
		deal(
			(
				card(Rank.ACE, Suit.SPADES),
				card(Rank.ACE, Suit.HEARTS),
			),
			(
				card(Rank.KING, Suit.SPADES),
				card(Rank.KING, Suit.HEARTS),
			),
		),
		deal(
			(
				card(Rank.FIVE, Suit.SPADES),
				card(Rank.FOUR, Suit.HEARTS),
			),
			(
				card(Rank.QUEEN, Suit.SPADES),
				card(Rank.QUEEN, Suit.HEARTS),
			),
		),
	))

	result = CFRTrainer(game).train(1)

	assert result.average_strategy
	for strategy in result.average_strategy.values():
		assert sum(strategy.values()) == pytest.approx(1.0)
		assert all(
			0.0 <= probability <= 1.0
			for probability in strategy.values()
		)


def test_restricted_holdem_rejects_duplicate_cards():
	ace_spades = card(Rank.ACE, Suit.SPADES)

	with pytest.raises(
		ValueError,
		match="duplicate cards",
	):
		RestrictedHeadsUpHoldemGame((
			HeadsUpHoldemDeal(
				hole_cards=(
					(
						ace_spades,
						card(Rank.ACE, Suit.HEARTS),
					),
					(
						ace_spades,
						card(Rank.KING, Suit.HEARTS),
					),
				),
				board=board(),
			),
		))
