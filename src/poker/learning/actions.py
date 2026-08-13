from dataclasses import dataclass

from poker.game.actions import PlayerAction


ACTION_ORDER = (
	PlayerAction.FOLD,
	PlayerAction.CHECK,
	PlayerAction.CALL,
	PlayerAction.BET,
	PlayerAction.RAISE,
	PlayerAction.ALL_IN,
)


@dataclass(frozen=True)
class LearningActionSpace:
	mask: tuple[float, ...]
	sizing: tuple[float, ...]
	action_names: tuple[str, ...] = tuple(action.value for action in ACTION_ORDER)

	@property
	def size(self):
		return len(self.mask)

	def allows(self, action):
		try:
			index = ACTION_ORDER.index(action)
		except ValueError:
			return False

		return bool(self.mask[index])


class LearningActionEncoder:
	ACTIONS = ACTION_ORDER
	ACTION_NAMES = tuple(action.value for action in ACTION_ORDER)

	def encode(self, legal_actions, hand_state):
		scale = self._scale(hand_state)
		mask = tuple(
			1.0 if action in legal_actions.actions else 0.0
			for action in self.ACTIONS
		)
		sizing = (
			legal_actions.call_amount / scale,
			self._normalized(legal_actions.min_bet, scale),
			self._normalized(legal_actions.max_bet, scale),
			self._normalized(legal_actions.min_raise_to, scale),
			self._normalized(legal_actions.max_raise_to, scale),
		)

		return LearningActionSpace(
			mask=mask,
			sizing=sizing,
		)

	def target(self, decision, legal_actions, hand_state):
		if not legal_actions.allows(decision.action, decision.amount):
			raise ValueError(
				f"Decision is not legal: {decision.action.value} {decision.amount}"
			)

		try:
			action_index = self.ACTIONS.index(decision.action)
		except ValueError as error:
			raise ValueError(
				f"Unsupported learning action: {decision.action}"
			) from error

		scale = self._scale(hand_state)
		return action_index, decision.amount / scale

	def _scale(self, hand_state):
		total_chips = sum(
			player.chips + player.total_contribution
			for player in hand_state.players
		)
		return float(total_chips or 1)

	def _normalized(self, value, scale):
		return float(value) / scale if value is not None else 0.0
