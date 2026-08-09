from poker.game.action_resolver import ActionResolver
from poker.game.actions import PlayerAction
from poker.player.player import Player


def test_action_resolver_bet():
	player = Player("Alice", 100)
	resolver = ActionResolver()

	resolver.apply(player, PlayerAction.BET, 25)

	assert player.chips == 75
	assert player.current_bet == 25


def test_action_resolver_fold():
	player = Player("Alice", 100)
	resolver = ActionResolver()

	resolver.apply(player, PlayerAction.FOLD)

	assert player.folded


def test_action_resolver_call_moves_chips_to_current_bet():
	player = Player("Alice", 100)
	resolver = ActionResolver()

	resolver.apply(player, PlayerAction.CALL, 15)

	assert player.chips == 85
	assert player.current_bet == 15
