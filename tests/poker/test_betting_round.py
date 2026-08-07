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
