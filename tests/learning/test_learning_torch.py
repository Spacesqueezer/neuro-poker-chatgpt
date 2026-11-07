import json
import pytest
import torch

from poker.learning.torch_dataset import PokerImitationDataset
from poker.learning.model import PokerPolicyNetwork
from poker.learning.trainer import ImitationTrainer

@pytest.fixture
def dummy_dataset(tmp_path):
	data = [
		{
			"version": 1,
			"observation": [0.1, 0.2, 0.3, 0.4],
			"action_mask": [1.0, 1.0, 0.0, 0.0, 0.0, 0.0],
			"action_sizing": [0.0, 0.0, 0.0, 0.0, 0.0],
			"action_index": 1,
			"action_amount": 0.0,
			"acting_player": "player_0",
			"opponent_order": ["player_1"]
		},
		{
			"version": 1,
			"observation": [0.4, 0.3, 0.2, 0.1],
			"action_mask": [1.0, 0.0, 1.0, 1.0, 0.0, 0.0],
			"action_sizing": [0.1, 0.2, 1.0, 0.0, 0.0],
			"action_index": 3,
			"action_amount": 0.5,
			"acting_player": "player_1",
			"opponent_order": ["player_0"]
		}
	]

	path = tmp_path / "dummy.jsonl"
	with open(path, "w") as f:
		for item in data:
			f.write(json.dumps(item) + "\n")

	return path


def test_poker_imitation_dataset_loading(dummy_dataset):
	dataset = PokerImitationDataset(dummy_dataset)
	assert len(dataset) == 2

	sample = dataset[0]
	assert torch.equal(sample["observation"], torch.tensor([0.1, 0.2, 0.3, 0.4], dtype=torch.float32))
	assert torch.equal(sample["action_mask"], torch.tensor([1.0, 1.0, 0.0, 0.0, 0.0, 0.0], dtype=torch.float32))
	assert sample["action_index"].item() == 1


def test_poker_policy_network_forward_and_masking():
	model = PokerPolicyNetwork(observation_size=4, action_classes=6, hidden_sizes=(16,))
	obs = torch.tensor([[0.1, 0.2, 0.3, 0.4]])
	mask = torch.tensor([[1.0, 1.0, 0.0, 0.0, 0.0, 0.0]])

	outputs = model(obs, action_mask=mask)
	logits = outputs["action_logits"]

	assert logits.shape == (1, 6)

	# Masked actions should have very large negative logits
	assert logits[0, 2].item() < -1e8
	assert logits[0, 3].item() < -1e8
	assert logits[0, 4].item() < -1e8
	assert logits[0, 5].item() < -1e8

	# Unmasked actions should be normal values
	assert logits[0, 0].item() > -1e8
	assert logits[0, 1].item() > -1e8


def test_imitation_trainer_training_step(dummy_dataset):
	dataset = PokerImitationDataset(dummy_dataset)
	model = PokerPolicyNetwork(observation_size=4, action_classes=6, hidden_sizes=(16,))

	trainer = ImitationTrainer(
		model=model,
		train_dataset=dataset,
		validation_dataset=dataset, # Use same for dummy test
		learning_rate=0.1,
		batch_size=2,
		device="cpu"
	)

	history = trainer.train(epochs=1)
	assert len(history) == 1
	metrics = history[0]

	assert "train_loss" in metrics
	assert "train_accuracy" in metrics
	assert "val_loss" in metrics
	assert "val_accuracy" in metrics
	assert metrics["train_loss"] >= 0.0

	# Verify sizing loss is included
	assert trainer.sizing_criterion is not None
