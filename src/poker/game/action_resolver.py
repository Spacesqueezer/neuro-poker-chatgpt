from poker.game.actions import PlayerAction


class ActionResolver:
	def can_act(self, player):
		return not player.folded

	def apply(self, player, action, amount=0):
		if not self.can_act(player):
			raise ValueError("Folded player cannot act")

		if action == PlayerAction.FOLD:
			player.fold()
			return

		if action in (PlayerAction.BET, PlayerAction.RAISE, PlayerAction.ALL_IN):
			player.bet(amount)
			return

		if action in (PlayerAction.CHECK, PlayerAction.CALL):
			return

		raise ValueError("Unsupported action")
