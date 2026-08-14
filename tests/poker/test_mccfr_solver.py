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
