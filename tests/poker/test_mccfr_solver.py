from dataclasses import dataclass

from poker.solver import ExternalSamplingMCCFR, MCCFRResult


@dataclass(frozen=True)
class MinimalNode:
	state: str = "terminal"
	probability: float = 1.0


class MinimalSolverGame:
	def initial_nodes(self):
		return (MinimalNode(),)

	def is_terminal_node(self, state):
		return True

	def terminal_node_utility(self, state, player):
		return 0.0



def test_mccfr_returns_result_for_positive_iterations():
	result = ExternalSamplingMCCFR(
		MinimalSolverGame()
	).train(10)

	assert isinstance(result, MCCFRResult)
	assert result.iterations == 10


def test_regret_matching_returns_normalized_strategy():
	solver = ExternalSamplingMCCFR(
		MinimalSolverGame()
	)

	strategy = solver._regret_matching(
		{
			"fold": 1.0,
			"call": 3.0,
		}
	)

	assert strategy["fold"] == 0.25
	assert strategy["call"] == 0.75


def test_seeded_sampling_is_reproducible():
	first = ExternalSamplingMCCFR(
		MinimalSolverGame(),
		seed=42,
	)
	second = ExternalSamplingMCCFR(
		MinimalSolverGame(),
		seed=42,
	)

	strategy = {
		"fold": 0.25,
		"call": 0.75,
	}

	assert first.random_choice(strategy) == second.random_choice(strategy)


def test_sampling_probability_is_not_greedy_only():
	solver = ExternalSamplingMCCFR(
		MinimalSolverGame(),
		seed=1,
	)

	strategy = {
		"fold": 0.9,
		"call": 0.1,
	}

	results = {
		solver.random_choice(strategy)
		for _ in range(50)
	}

	assert "fold" in results
