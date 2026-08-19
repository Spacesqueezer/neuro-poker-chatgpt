import pytest
from pathlib import Path

from poker.learning.rl_dataset import RLDatasetCapture
from poker.learning.self_play import ModelPool
from poker.api import ActionDecision
from poker.game.actions import PlayerAction

class DummyWriter:
	def __init__(self):
		self.samples = []

	def write(self, sample):
		self.samples.append(sample)


def test_model_pool_samples_historical_models(tmp_path):
	pool_dir = tmp_path / "models"
	pool = ModelPool(pool_dir)

	# Empty pool
	assert pool.sample_model() is None

	# Add models
	m1 = tmp_path / "model1.pt"
	m1.write_text("dummy")
	pool.add_model(m1)

	m2 = tmp_path / "model2.pt"
	m2.write_text("dummy")
	pool.add_model(m2)

	sampled = pool.sample_model(seed=42)
	assert sampled.name in ("model1.pt", "model2.pt")
	assert len(pool.list_models()) == 2


def test_rl_dataset_capture_buffers_and_assigns_reward():
	writer = DummyWriter()
	capture = RLDatasetCapture(writer)

	# Mock hand state and decision
	class MockHandState:
		acting_player = "player_1"
		players = [
			type("Player", (), {"name": "player_1", "chips": 100, "current_bet": 0, "total_contribution": 0, "folded": False, "position": "SB"}),
			type("Player", (), {"name": "player_2", "chips": 100, "current_bet": 0, "total_contribution": 0, "folded": False, "position": "BB"})
		]
		street = "preflop"
		hole_cards = ()
		board = ()
		pot = 0
		target_bet = 0
		minimum_raise = 0
		dealer = "player_1"
		small_blind = "player_1"
		big_blind = "player_2"
		action_history = []

	class MockLegalActions:
		actions = (PlayerAction.FOLD,)
		call_amount = 0
		min_bet = None
		max_bet = None
		min_raise_to = None
		max_raise_to = None
		def allows(self, a, am): return True

	class MockHistory:
		final_stacks = {"player_1": 150, "player_2": 50}
		players = [
			{"name": "player_1", "starting_chips": 100},
			{"name": "player_2", "starting_chips": 100}
		]

	hand_state = MockHandState()
	legal = MockLegalActions()
	decision = ActionDecision(PlayerAction.FOLD)

	# Observe decision
	capture.decision_observer(hand_state, legal, decision)

	# Nothing written yet
	assert len(writer.samples) == 0
	assert len(capture.hand_buffer) == 1

	# Observe end of hand
	history = MockHistory()
	capture.hand_observer(history)

	# Sample written with correct reward
	assert len(writer.samples) == 1
	sample = writer.samples[0]
	assert sample.acting_player == "player_1"
	# player_1 went from 100 to 150 -> reward = 50
	assert sample.reward == 50
