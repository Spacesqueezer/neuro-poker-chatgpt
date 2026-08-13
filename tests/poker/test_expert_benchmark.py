from poker.arena.benchmark import (
	ExpertBenchmarkConfig,
	ExpertBenchmarkRunner,
)


def test_expert_benchmark_is_reproducible():
	config = ExpertBenchmarkConfig(
		sessions=3,
		hands_per_session=8,
		starting_stack=100,
		seed=123,
		equity_samples=20,
		opponents=("calling_station", "nit"),
	)
	runner = ExpertBenchmarkRunner()

	first = runner.run(config)
	second = runner.run(config)

	assert first.to_dict() == second.to_dict()

	for matchup in first.matchups:
		assert matchup.sessions == 3
		assert matchup.requested_hands == 24
		assert matchup.hands > 0
		assert matchup.failed_hands == 0
		assert 0.0 < matchup.completion_rate <= 1.0


def test_expert_benchmark_aggregates_reset_sessions():
	config = ExpertBenchmarkConfig(
		sessions=4,
		hands_per_session=5,
		starting_stack=40,
		seed=7,
		equity_samples=10,
		opponents=("random",),
	)

	result = ExpertBenchmarkRunner().run(config)
	matchup = result.matchups[0]

	assert matchup.opponent == "random"
	assert matchup.sessions == 4
	assert matchup.requested_hands == 20
	assert matchup.hands > 0
	assert matchup.failed_hands == 0
	assert isinstance(matchup.expert_profit, int)
	assert isinstance(matchup.bb_per_100, float)


def test_expert_benchmark_rejects_invalid_config():
	runner = ExpertBenchmarkRunner()

	for config, expected in (
		(
			ExpertBenchmarkConfig(sessions=0),
			"sessions must be positive",
		),
		(
			ExpertBenchmarkConfig(hands_per_session=0),
			"hands_per_session must be positive",
		),
		(
			ExpertBenchmarkConfig(equity_samples=0),
			"equity_samples must be positive",
		),
		(
			ExpertBenchmarkConfig(opponents=("nit", "nit")),
			"opponents must be unique",
		),
	):
		try:
			runner.run(config)
		except ValueError as error:
			assert expected in str(error)
		else:
			raise AssertionError("Expected benchmark validation")
