class BettingRound:
	def __init__(self, players):
		self.players = players
		self.acted_players = set()
		self.raise_locked_players = set()
		self.last_action_target = {}

	def mark_action(
		self,
		player,
		bet_increased=False,
		full_raise=False,
		short_raise=False,
		target_bet=None,
	):
		if target_bet is None:
			target_bet = player.current_bet
		self.last_action_target[player] = target_bet

		if full_raise:
			self.acted_players = {player}
			self.raise_locked_players.clear()
			return

		if short_raise:
			self.raise_locked_players.update(self.acted_players)
			self.acted_players.add(player)
			return

		if bet_increased:
			self.acted_players = {player}
			return

		self.acted_players.add(player)

	def can_raise(self, player, current_target=None, minimum_raise=None):
		if player not in self.raise_locked_players:
			return True

		if current_target is None or minimum_raise is None:
			return False

		last_target = self.last_action_target.get(player)
		if last_target is None:
			return True

		return current_target - last_target >= minimum_raise

	def active_players(self):
		return [player for player in self.players if not getattr(player, "folded", False)]

	def is_complete(self):
		active_players = self.active_players()

		if not active_players:
			return False

		if len(active_players) == 1:
			return True

		target_bet = max(player.current_bet for player in active_players)

		return all(
			player in self.acted_players and player.current_bet == target_bet
			for player in active_players
			if player.chips > 0
		)

	def reset(self):
		self.acted_players.clear()
		self.raise_locked_players.clear()
		self.last_action_target.clear()
