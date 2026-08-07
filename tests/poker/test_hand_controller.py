from poker.game.dealer import Dealer
from poker.game.game_state import GameState
from poker.game.hand_controller import HandController


def test_hand_controller_deals_first_cards():
	state = GameState()
	state.add_player()
	state.add_player()

	controller = HandController(Dealer())
	controller.start_hand(state)

	assert len(state.players[0].cards) == 2
	assert len(state.players[1].cards) == 2


def test_hand_controller_advances_to_flop():
	state = GameState()
	state.add_player()

	controller = HandController(Dealer())
	controller.start_hand(state)
	controller.advance_street(state)

	assert len(state.board.cards) == 3
