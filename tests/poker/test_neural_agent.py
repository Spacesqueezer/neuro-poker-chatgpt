import pytest
import torch
import random
from unittest.mock import MagicMock

from poker.agents import NeuralAgent
from poker.api import ActionDecision, LegalActions, HandStateView, PublicPlayerView
from poker.game.actions import PlayerAction
from poker.learning.model import PokerPolicyNetwork


@pytest.fixture
def dummy_weights_file(tmp_path):
	# Create a dummy model and save weights
	model = PokerPolicyNetwork(observation_size=10, action_classes=6)
	path = tmp_path / "dummy_weights.pt"
	torch.save(model.state_dict(), path)
	return path


@pytest.fixture
def dummy_hand_state():
	return HandStateView(
		street="preflop",
		acting_player="player_1",
		hole_cards=("A♠", "K♠"),
		board=(),
		pot=3,
		target_bet=2,
		minimum_raise=2,
		dealer="player_0",
		small_blind="player_0",
		big_blind="player_1",
		players=(
			PublicPlayerView(
				name="player_0",
				chips=99,
				current_bet=1,
				total_contribution=1,
				folded=False,
				position="SB"
			),
			PublicPlayerView(
				name="player_1",
				chips=98,
				current_bet=2,
				total_contribution=2,
				folded=False,
				position="BB"
			)
		)
	)

def test_neural_agent_initialization(dummy_weights_file):
	agent = NeuralAgent(model_path=dummy_weights_file)
	assert agent.model is not None
	assert agent.model.observation_size == 10


def test_neural_agent_chooses_legal_action(dummy_weights_file, dummy_hand_state):
	# Mock encoders to return predictable sizes and values
	mock_obs_encoder = MagicMock()
	mock_obs_encoder.encode.return_value = MagicMock(values=[0.0] * 10)

	mock_action_encoder = MagicMock()
	mock_action_encoder.encode.return_value = MagicMock(mask=[1.0, 1.0, 1.0, 0.0, 1.0, 1.0], sizing=[0.0, 0.0, 0.0, 0.0, 0.0])
	mock_action_encoder.ACTION_NAMES = ("fold", "check", "call", "bet", "raise", "all_in")
	mock_action_encoder._scale.return_value = 100.0

	agent = NeuralAgent(
		model_path=dummy_weights_file,
		observation_encoder=mock_obs_encoder,
		action_encoder=mock_action_encoder
	)

	legal = LegalActions(
		actions=(PlayerAction.FOLD, PlayerAction.CALL, PlayerAction.RAISE, PlayerAction.ALL_IN),
		call_amount=1,
		min_raise_to=4,
		max_raise_to=100
	)

	decision = agent.choose_action(dummy_hand_state, legal)

	assert isinstance(decision, ActionDecision)
	assert decision.action in legal.actions

	if decision.action == PlayerAction.RAISE:
		assert 4 <= decision.amount <= 100
	elif decision.action == PlayerAction.CALL:
		assert decision.amount == 1
	else:
		assert decision.amount == 0

def test_neural_agent_stochastic_sampling(dummy_weights_file, dummy_hand_state):
	mock_obs_encoder = MagicMock()
	mock_obs_encoder.encode.return_value = MagicMock(values=[0.0] * 10)

	mock_action_encoder = MagicMock()
	mock_action_encoder.encode.return_value = MagicMock(mask=[1.0, 1.0, 1.0, 0.0, 1.0, 1.0], sizing=[0.0, 0.0, 0.0, 0.0, 0.0])
	mock_action_encoder.ACTION_NAMES = ("fold", "check", "call", "bet", "raise", "all_in")
	mock_action_encoder._scale.return_value = 100.0

	agent = NeuralAgent(
		model_path=dummy_weights_file,
		observation_encoder=mock_obs_encoder,
		action_encoder=mock_action_encoder,
		stochastic=True
	)

	legal = LegalActions(
		actions=(PlayerAction.FOLD, PlayerAction.CALL, PlayerAction.RAISE, PlayerAction.ALL_IN),
		call_amount=1,
		min_raise_to=4,
		max_raise_to=100
	)

	decision = agent.choose_action(dummy_hand_state, legal)
	assert isinstance(decision, ActionDecision)
	assert decision.action in legal.actions
