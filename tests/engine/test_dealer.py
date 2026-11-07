from poker.game.dealer import Dealer
from poker.game.game_state import GameState
from poker.player.player import Player


def test_dealer_deals_two_cards_to_players():
	state = GameState()
	state.add_player(Player("Alice", 100))
	state.add_player(Player("Bob", 100))

	dealer = Dealer()
	dealer.start_hand(state)

	assert len(state.players[0].hand.cards) == 2
	assert len(state.players[1].hand.cards) == 2


def test_dealer_resets_player_hand_state_before_dealing():
	state = GameState()
	player = Player("Alice", 100)
	player.bet(25)
	player.fold()
	state.add_player(player)

	dealer = Dealer()
	dealer.start_hand(state)

	assert player.current_bet == 0
	assert not player.folded
	assert len(player.hand.cards) == 2


def test_dealer_deals_flop():
	state = GameState()

	dealer = Dealer()
	dealer.start_hand(state)
	dealer.deal_flop(state)

	assert len(state.board.cards) == 3
