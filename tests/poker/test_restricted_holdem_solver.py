import pytest

from poker.cards.card import Card
from poker.enums import Rank, Suit
from poker.solver import (
	CFRTrainer,
	HeadsUpHoldemDeal,
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
	call = game.next_node(root, "call")
	raise_call = game.next_node(
		game.next_node(root, "raise"),
		"call",
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
	assert game.is_terminal_node(
		game.next_node(root, "call")
	)


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

	result = CFRTrainer(game).train(500)

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
