from poker.api import ActionDecision


class NitAgent:
	def choose_action(self, state, legal):
		for action in legal.actions:
			if action.value == "fold":
				return ActionDecision(action)

		return ActionDecision(legal.actions[0])
