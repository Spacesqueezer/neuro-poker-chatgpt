from poker.game.betting_round import BettingRound
from poker.player.player import Player


def test_betting_round_finishes_after_all_players_act():
	first = Player("Alice", 100)
	second = Player("Bob", 100)

	round_state = BettingRound([first, second])

	round_state.mark_action(first)
	assert not round_state.is_complete()

	round_state.mark_action(second)
	assert round_state.is_complete()


def test_folded_players_do_not_block_round():
	first = Player("Alice", 100)
	second = Player("Bob", 100)

	second.fold()

	round_state = BettingRound([first, second])
	round_state.mark_action(first)

	assert round_state.is_complete()


def test_raise_requires_previous_players_to_act_again():
	first = Player("Alice", 100)
	second = Player("Bob", 100)
	third = Player("Carol", 100)
	first.bet(10)
	second.bet(10)
	third.bet(20)

	round_state = BettingRound([first, second, third])
	round_state.mark_action(first)
	round_state.mark_action(second)
	round_state.mark_action(third, bet_increased=True)

	assert not round_state.is_complete()

	first.bet(10)
	round_state.mark_action(first)
	second.bet(10)
	round_state.mark_action(second)

	assert round_state.is_complete()


def test_short_raise_locks_players_who_already_acted():
	first = Player("Alice", 100)
	second = Player("Bob", 100)
	third = Player("Carol", 100)
	round_state = BettingRound([first, second, third])

	round_state.mark_action(first)
	round_state.mark_action(second, short_raise=True)

	assert not round_state.can_raise(first)
	assert round_state.can_raise(third)


def test_full_raise_reopens_raise_rights_after_short_raise():
	first = Player("Alice", 100)
	second = Player("Bob", 100)
	third = Player("Carol", 100)
	round_state = BettingRound([first, second, third])

	round_state.mark_action(first)
	round_state.mark_action(second, short_raise=True)
	assert not round_state.can_raise(first)

	round_state.mark_action(third, full_raise=True)

	assert round_state.can_raise(first)
	assert round_state.can_raise(second)

def test_cumulative_short_all_ins_reopen_for_player_facing_full_raise():
	alice = Player("Alice", 100)
	bob = Player("Bob", 0)
	carol = Player("Carol", 100)
	dave = Player("Dave", 0)
	round_state = BettingRound([alice, bob, carol, dave])

	alice.current_bet = 100
	round_state.mark_action(alice, target_bet=100)

	bob.current_bet = 125
	round_state.mark_action(bob, short_raise=True, target_bet=125)

	carol.current_bet = 125
	round_state.mark_action(carol, target_bet=125)

	dave.current_bet = 200
	round_state.mark_action(dave, short_raise=True, target_bet=200)

	assert round_state.can_raise(alice, current_target=200, minimum_raise=100)
	assert not round_state.can_raise(carol, current_target=200, minimum_raise=100)


def test_call_after_cumulative_reopen_resets_player_reopen_baseline():
	alice = Player("Alice", 100)
	bob = Player("Bob", 0)
	carol = Player("Carol", 0)
	round_state = BettingRound([alice, bob, carol])

	alice.current_bet = 100
	round_state.mark_action(alice, target_bet=100)

	bob.current_bet = 150
	round_state.mark_action(bob, short_raise=True, target_bet=150)
	carol.current_bet = 200
	round_state.mark_action(carol, short_raise=True, target_bet=200)

	assert round_state.can_raise(alice, current_target=200, minimum_raise=100)

	alice.current_bet = 200
	round_state.mark_action(alice, target_bet=200)

	assert not round_state.can_raise(alice, current_target=250, minimum_raise=100)

