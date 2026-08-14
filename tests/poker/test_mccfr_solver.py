from poker.solver import ExternalSamplingMCCFR, MCCFRResult


class MinimalSolverGame:
	def initial_nodes(self):
		return []



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
