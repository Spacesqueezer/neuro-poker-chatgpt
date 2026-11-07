from poker.solver import CFRTrainer, KuhnPokerGame, RegretMatching


def test_regret_matching_uses_only_positive_regret():
	strategy = RegretMatching().strategy({
		"check": -2.0,
		"bet": 3.0,
	})

	assert strategy == {
		"check": 0.0,
		"bet": 1.0,
	}


def test_regret_matching_falls_back_to_uniform_strategy():
	strategy = RegretMatching().strategy({
		"check": -2.0,
		"bet": 0.0,
	})

	assert strategy == {
		"check": 0.5,
		"bet": 0.5,
	}


def test_kuhn_terminal_utilities_are_zero_sum():
	game = KuhnPokerGame()
	cards = (2, 0)

	for history in (
		("check", "check"),
		("bet", "check"),
		("bet", "bet"),
		("check", "bet", "check"),
		("check", "bet", "bet"),
	):
		assert (
			game.terminal_utility(cards, history, 0)
			== -game.terminal_utility(cards, history, 1)
		)


def test_cfr_training_is_deterministic_and_normalized():
	first = CFRTrainer().train(2000)
	second = CFRTrainer().train(2000)

	assert first.average_strategy == second.average_strategy
	assert first.current_strategy == second.current_strategy
	assert first.cumulative_regret == second.cumulative_regret

	for strategy in first.average_strategy.values():
		assert abs(sum(strategy.values()) - 1.0) < 1e-12
		assert all(
			0.0 <= probability <= 1.0
			for probability in strategy.values()
		)


def test_cfr_learns_kuhn_equilibrium_value():
	result = CFRTrainer().train(20000)

	assert abs(result.average_utility + 1.0 / 18.0) < 0.02


def test_cfr_average_strategy_contains_all_kuhn_information_sets():
	result = CFRTrainer().train(2000)

	assert len(result.average_strategy) == 12
