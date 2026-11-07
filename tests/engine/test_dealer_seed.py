from poker.game.dealer import Dealer
from poker.game.game_state import GameState
from poker.player.player import Player


def make_state():
	state = GameState()
	state.add_player(Player("Alice", 100))
	state.add_player(Player("Bob", 100))
	return state


def test_same_seed_deals_same_cards():
	state_a = make_state()
	state_b = make_state()
	dealer_a = Dealer(seed=12345)
	dealer_b = Dealer(seed=12345)

	dealer_a.start_hand(state_a)
	dealer_b.start_hand(state_b)

	cards_a = [[str(card) for card in player.hand.cards] for player in state_a.players]
	cards_b = [[str(card) for card in player.hand.cards] for player in state_b.players]
	assert cards_a == cards_b
	assert dealer_a.current_seed == 12345
	assert dealer_b.current_seed == 12345


def test_next_hand_uses_next_seed():
	state = make_state()
	dealer = Dealer(seed=100)

	dealer.start_hand(state)
	assert dealer.current_seed == 100

	state.deck.reset()
	dealer.start_hand(state)
	assert dealer.current_seed == 101
