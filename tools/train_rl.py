import argparse
from pathlib import Path

import torch

from poker.learning.model import PokerPolicyNetwork
from poker.learning.rl_trainer import PolicyGradientTrainer
from poker.learning.torch_dataset import PokerImitationDataset


def main():
	parser = argparse.ArgumentParser(description="Train model using Reinforcement Learning (Policy Gradient)")
	parser.add_argument("--train", required=True, help="Path to train JSONL dataset with rewards")
	parser.add_argument("--base-model", required=True, help="Path to initial model weights (.pt)")
	parser.add_argument("--output", required=True, help="Path to save the trained model weights (.pt)")
	parser.add_argument("--epochs", type=int, default=5, help="Number of training epochs")
	parser.add_argument("--batch-size", type=int, default=32, help="Training batch size")
	parser.add_argument("--learning-rate", type=float, default=1e-4, help="Learning rate")
	parser.add_argument("--value-weight", type=float, default=0.5, help="Weight for Value Loss")
	parser.add_argument("--entropy-weight", type=float, default=0.01, help="Weight for Entropy bonus")

	args = parser.parse_args()

	train_dataset = PokerImitationDataset(args.train)

	if len(train_dataset) == 0:
		raise ValueError("Training dataset is empty.")

	obs_size = train_dataset[0]["observation"].size(0)

	device = "cuda" if torch.cuda.is_available() else "cpu"
	print(f"Using device: {device}")

	model = PokerPolicyNetwork(observation_size=obs_size)
	state_dict = torch.load(args.base_model, map_location=device, weights_only=True)
	model.load_state_dict(state_dict)
	print(f"Loaded base model from {args.base_model}")

	trainer = PolicyGradientTrainer(
		model=model,
		train_dataset=train_dataset,
		learning_rate=args.learning_rate,
		batch_size=args.batch_size,
		value_weight=args.value_weight,
		entropy_weight=args.entropy_weight,
		device=device
	)

	print(f"Starting RL training for {args.epochs} epochs...")
	history = trainer.train(epochs=args.epochs)

	final_metrics = history[-1]
	print(f"Training finished. Final metrics: {final_metrics}")

	output_path = Path(args.output)
	output_path.parent.mkdir(parents=True, exist_ok=True)
	torch.save(model.state_dict(), output_path)
	print(f"Model saved to {output_path}")

if __name__ == "__main__":
	main()
