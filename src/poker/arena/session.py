from dataclasses import dataclass, field

from poker.api import play_hand


@dataclass
class ArenaSession:
	starting_stack: int
	stacks: dict[str, int] = field(default_factory=dict)
	completed_hands: int = 0

	def current_stacks(self):
		return dict(self.stacks)

	def is_finished(self):
		return any(stack <= 0 for stack in self.stacks.values())

	@classmethod
	def create(cls, players, starting_stack):
		return cls(
			starting_stack=starting_stack,
			stacks={name: starting_stack for name in players},
		)

	def apply_hand_result(self, history):
		if not history.final_stacks:
			raise ValueError("Completed hand has no final stacks")

		if set(history.final_stacks) != set(self.stacks):
			raise ValueError("Hand result players do not match Arena session")

		chips_before = sum(self.stacks.values())
		chips_after = sum(history.final_stacks.values())
		if chips_after != chips_before:
			raise ValueError(
				f"Chip conservation failed: before={chips_before}, after={chips_after}"
			)

		if any(stack < 0 for stack in history.final_stacks.values()):
			raise ValueError("Hand result contains a negative stack")

		self.stacks = dict(history.final_stacks)
		self.completed_hands += 1

	def play_next_hand(
		self,
		agents,
		seed,
		dealer_name,
		decision_observer=None,
	):
		kwargs = {
			"seed": seed,
			"starting_stacks": self.current_stacks(),
			"dealer_name": dealer_name,
		}
		if decision_observer is not None:
			kwargs["decision_observer"] = decision_observer

		result = play_hand(
			agents,
			**kwargs,
		)
		self.apply_hand_result(result)
		return result

	def run(
		self,
		agents,
		hands,
		seed,
		stats,
		hand_observer=None,
		decision_observer=None,
	):
		players = list(agents)

		for index in range(hands):
			if self.is_finished():
				break

			current_seed = seed + index
			try:
				result = self.play_next_hand(
					agents,
					seed=current_seed,
					dealer_name=players[index % len(players)],
					decision_observer=decision_observer,
				)
				stats.record_result(current_seed, result)
			except Exception:
				stats.failed_hands += 1
				continue

			if hand_observer is not None:
				hand_observer(result)
