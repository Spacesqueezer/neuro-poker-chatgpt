from poker.arena.runner import ArenaRunner
from poker.agents import RandomAgent, NitAgent


def test_arena_can_run_baseline_match():
	agents = {
		"random": RandomAgent(seed=42),
		"nit": NitAgent(),
	}

	runner = ArenaRunner(agents, starting_stack=100)
	result = runner.run(100, seed=42).summary()

	assert result["hands"] > 0
	assert result["failed_hands"] >= 0
	assert "bb_per_100" in result
	assert set(result["players"]) == {"random", "nit"}
