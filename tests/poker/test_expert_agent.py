from poker.api.hand_state import HandStateView, LegalActions, PublicPlayerView
from poker.agents.expert import ExpertAgent, MonteCarloEquityEstimator
from poker.game.actions import PlayerAction
from poker.strategy.ranges import UniformRangeModel


def _state(hole_cards, board=()):
	return HandStateView(
		street="preflop" if not board else "flop",
		acting_player="hero",
		hole_cards=hole_cards,
		board=board,
		pot=12,
		target_bet=4,
		minimum_raise=4,
		dealer="villain",
		small_blind="hero",
		big_blind="villain",
		players=(
			PublicPlayerView(
				name="hero", chips=96, current_bet=2, total_contribution=4,
				folded=False, position="BB",
			),
			PublicPlayerView(
				name="villain", chips=94, current_bet=4, total_contribution=6,
				folded=False, position="BTN",
			),
		),
	)


def test_equity_estimator_is_reproducible_for_same_seed():
	first = MonteCarloEquityEstimator(samples=100, seed=123)
	second = MonteCarloEquityEstimator(samples=100, seed=123)
	state = _state(("A♠", "A♥"))

	assert first.estimate(state) == second.estimate(state)


def test_equity_estimator_can_use_explicit_uniform_range_model():
	estimator = MonteCarloEquityEstimator(
		samples=50,
		seed=123,
		range_model=UniformRangeModel(),
	)

	equity = estimator.estimate(
		_state(("A♠", "A♥"))
	)

	assert 0.0 <= equity <= 1.0


def test_premium_pair_has_more_equity_than_weak_offsuit_hand():
	premium = MonteCarloEquityEstimator(samples=300, seed=7).estimate(
		_state(("A♠", "A♥"))
	)
	weak = MonteCarloEquityEstimator(samples=300, seed=7).estimate(
		_state(("7♠", "2♥"))
	)

	assert premium > weak
	assert premium > 0.7


def test_expert_agent_always_returns_legal_decision():
	legal = LegalActions(
		actions=(PlayerAction.FOLD, PlayerAction.CALL, PlayerAction.RAISE, PlayerAction.ALL_IN),
		call_amount=2, min_raise_to=8, max_raise_to=98,
	)
	agent = ExpertAgent(seed=42, equity_samples=50)

	for hole_cards in (("A♠", "A♥"), ("K♠", "Q♠"), ("7♠", "2♥")):
		decision = agent.choose_action(_state(hole_cards), legal)
		assert legal.allows(decision.action, decision.amount)
