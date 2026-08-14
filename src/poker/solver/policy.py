class RestrictedSolverPolicy:
	def __init__(self, lookup):
		self.lookup = lookup

	def strategy_for_node(self, game, state):
		if game.is_terminal_node(state):
			raise ValueError("terminal solver node has no policy")

		player = game.player_to_act(state)
		legal_actions = tuple(game.legal_actions(state))
		if not legal_actions:
			raise ValueError("solver node has no legal actions")

		information_set = game.information_set_for_node(
			state,
			player,
		)
		stored = self.lookup.lookup(information_set)

		if stored is None:
			return self._uniform_strategy(legal_actions)

		reconciled = {
			action: stored[action]
			for action in legal_actions
			if action in stored
		}
		total = sum(reconciled.values())

		if total <= 0.0:
			return self._uniform_strategy(legal_actions)

		return {
			action: reconciled.get(action, 0.0) / total
			for action in legal_actions
		}

	def choose_action(self, game, state):
		strategy = self.strategy_for_node(game, state)
		legal_actions = tuple(game.legal_actions(state))
		return max(
			legal_actions,
			key=lambda action: strategy[action],
		)

	def _uniform_strategy(self, legal_actions):
		probability = 1.0 / len(legal_actions)
		return {
			action: probability
			for action in legal_actions
		}
