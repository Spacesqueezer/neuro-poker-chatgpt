import pytest

from poker.agents.maniac import ManiacAgent
from poker.agents.tag import TAGAgent
from poker.agents.lag import LAGAgent
from poker.api import ActionDecision, LegalActions, HandStateView, PublicPlayerView
from poker.game.actions import PlayerAction

@pytest.fixture
def dummy_state_preflop_weak():
	return HandStateView(
		street="preflop",
		acting_player="player_1",
		hole_cards=("2♠", "7♣"),
		board=(),
		pot=3,
		target_bet=2,
		minimum_raise=2,
		dealer="player_0",
		small_blind="player_0",
		big_blind="player_1",
		players=()
	)

@pytest.fixture
def dummy_state_preflop_strong():
	return HandStateView(
		street="preflop",
		acting_player="player_1",
		hole_cards=("A♠", "A♣"),
		board=(),
		pot=3,
		target_bet=2,
		minimum_raise=2,
		dealer="player_0",
		small_blind="player_0",
		big_blind="player_1",
		players=()
	)

@pytest.fixture
def full_legal_actions():
	return LegalActions(
		actions=(PlayerAction.FOLD, PlayerAction.CHECK, PlayerAction.CALL, PlayerAction.BET, PlayerAction.RAISE, PlayerAction.ALL_IN),
		call_amount=2,
		min_bet=2,
		max_bet=100,
		min_raise_to=4,
		max_raise_to=100
	)

def test_maniac_agent_is_aggressive(dummy_state_preflop_weak, full_legal_actions):
	# Test with multiple seeds to catch random branches
	aggressive_actions = 0
	for i in range(10):
		agent = ManiacAgent(seed=i)
		decision = agent.choose_action(dummy_state_preflop_weak, full_legal_actions)
		assert isinstance(decision, ActionDecision)
		if decision.action in (PlayerAction.BET, PlayerAction.RAISE, PlayerAction.ALL_IN):
			aggressive_actions += 1

	# Maniac should always try to be aggressive if those actions are available
	assert aggressive_actions == 10

def test_tag_agent_folds_weak_preflop(dummy_state_preflop_weak, full_legal_actions):
	agent = TAGAgent(seed=42)
	decision = agent.choose_action(dummy_state_preflop_weak, full_legal_actions)
	assert decision.action in (PlayerAction.CHECK, PlayerAction.FOLD)

def test_tag_agent_raises_strong_preflop(dummy_state_preflop_strong, full_legal_actions):
	agent = TAGAgent(seed=42)
	decision = agent.choose_action(dummy_state_preflop_strong, full_legal_actions)
	assert decision.action in (PlayerAction.BET, PlayerAction.RAISE)

def test_lag_agent_mixes_actions(dummy_state_preflop_weak, full_legal_actions):
	agent = LAGAgent(seed=42)

	# Since it's randomized, we just ensure it returns a valid ActionDecision
	# and doesn't crash on standard inputs.
	decision = agent.choose_action(dummy_state_preflop_weak, full_legal_actions)
	assert isinstance(decision, ActionDecision)
	assert decision.action in full_legal_actions.actions
