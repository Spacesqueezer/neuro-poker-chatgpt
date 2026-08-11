from dataclasses import dataclass, field


@dataclass
class ArenaSession:
	starting_stack: int
	stacks: dict[str, int] = field(default_factory=dict)

	def current_stacks(self):
		return dict(self.stacks)

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
