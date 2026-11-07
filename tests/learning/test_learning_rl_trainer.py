import json
import pytest
import torch
from poker.learning.model import PokerPolicyNetwork
from poker.learning.torch_dataset import PokerImitationDataset
from poker.learning.rl_trainer import PolicyGradientTrainer

@pytest.fixture
def dummy_rl_dataset(tmp_path):
	data = [
		{
			"version": 1,
			"observation": [0.1, 0.2, 0.3, 0.4],
			"action_mask": [1.0, 1.0, 0.0, 0.0, 0.0, 0.0],
			"action_sizing": [0.0, 0.0, 0.0, 0.0, 0.0],
			"action_index": 1,
			"action_amount": 0.0,
			"acting_player": "player_0",
			"opponent_order": ["player_1"],
			"reward": 10.0
		},
		{
			"version": 1,
			"observation": [0.4, 0.3, 0.2, 0.1],
			"action_mask": [1.0, 0.0, 1.0, 1.0, 0.0, 0.0],
			"action_sizing": [0.1, 0.2, 1.0, 0.0, 0.0],
			"action_index": 3,
			"action_amount": 0.5,
			"acting_player": "player_1",
			"opponent_order": ["player_0"],
			"reward": -5.0
		}
	]

	path = tmp_path / "dummy_rl.jsonl"
	with open(path, "w") as f:
		for item in data:
			f.write(json.dumps(item) + "\n")

	return path


def test_rl_dataset_includes_reward(dummy_rl_dataset):
	dataset = PokerImitationDataset(dummy_rl_dataset)
	assert len(dataset) == 2

	sample = dataset[0]
	assert "reward" in sample
	assert sample["reward"].item() == 10.0

	sample2 = dataset[1]
	assert sample2["reward"].item() == -5.0


def test_policy_gradient_trainer_training_step(dummy_rl_dataset):
	dataset = PokerImitationDataset(dummy_rl_dataset)
	model = PokerPolicyNetwork(observation_size=4, action_classes=6, hidden_sizes=(16,))

	trainer = PolicyGradientTrainer(
		model=model,
		train_dataset=dataset,
		learning_rate=0.1,
		batch_size=2,
		device="cpu"
	)

	history = trainer.train(epochs=1)
	assert len(history) == 1
	metrics = history[0]

	assert "loss" in metrics
	assert "pg_loss" in metrics
	assert "value_loss" in metrics
	assert "entropy" in metrics

	# Value loss should be non-negative
	assert metrics["value_loss"] >= 0.0

	# Entropy should be positive
	assert metrics["entropy"] >= 0.0
