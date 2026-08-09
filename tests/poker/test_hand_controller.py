from poker.game.dealer import Dealer
from poker.game.game_state import GameState
from poker.game.hand_controller import HandController
from poker.player.player import Player


def test_hand_controller_deals_first_cards():
	state = GameState()
	state.add_player(Player("Alice", 100))
	state.add_player(Player("Bob", 100))

	controller = HandController(Dealer())
	controller.start_hand(state)

	assert len(state.players[0].hand.cards) == 2
	assert len(state.players[1].hand.cards) == 2


def test_hand_controller_advances_to_flop():
	state = GameState()
	state.add_player(Player("Alice", 100))

	controller = HandController(Dealer())
	controller.start_hand(state)
	controller.advance_street(state)

	assert len(state.board.cards) == 3
