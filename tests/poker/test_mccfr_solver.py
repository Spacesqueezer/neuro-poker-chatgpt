from poker.solver import ExternalSamplingMCCFR, MCCFRResult


def test_mccfr_returns_result_for_positive_iterations():
	result = ExternalSamplingMCCFR(object()).train(10)

	assert isinstance(result, MCCFRResult)
	assert result.iterations == 10
