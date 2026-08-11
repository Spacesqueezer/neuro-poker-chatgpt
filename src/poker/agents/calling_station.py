from poker.api import ActionDecision


class CallingStationAgent:
	def choose_action(self, state, legal):
		if legal.call_amount is not None and "call" in [action.value for action in legal.actions]:
			for action in legal.actions:
				if action.value == "call":
					return ActionDecision(action)

		return ActionDecision(legal.actions[0])
