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
			return

		for name, stack in history.final_stacks.items():
			self.stacks[name] = stack

		self.completed_hands += 1

	def play_next_hand(self, agents, seed, dealer_name):
		result = play_hand(
			agents,
			seed=seed,
			starting_stack=self.starting_stack,
			dealer_name=dealer_name,
		)
		self.apply_hand_result(result)
		return result
