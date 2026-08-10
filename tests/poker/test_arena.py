from poker.api import ActionDecision
from poker.arena.runner import ArenaRunner


class CheckAgent:
	def choose_action(self, state, legal):
		return ActionDecision(legal.actions[0])


def test_arena_runs_multiple_hands():
	runner = ArenaRunner({
		"alice": CheckAgent(),
		"bob": CheckAgent(),
	})

	result = runner.run(2, seed=42)

	assert result.hands == 2
	assert result.seeds == [42, 43]
