import argparse
from pathlib import Path

import torch

from poker.learning.model import PokerPolicyNetwork
from poker.learning.torch_dataset import PokerImitationDataset
from poker.learning.trainer import ImitationTrainer


def main():
	parser = argparse.ArgumentParser(description="Train an imitation learning model.")
	parser.add_argument("--train", required=True, help="Path to train JSONL dataset")
	parser.add_argument("--validation", required=True, help="Path to validation JSONL dataset")
	parser.add_argument("--output", required=True, help="Path to save the trained model weights (.pt)")
	parser.add_argument("--epochs", type=int, default=10, help="Number of training epochs")
	parser.add_argument("--batch-size", type=int, default=32, help="Training batch size")
	parser.add_argument("--learning-rate", type=float, default=1e-3, help="Learning rate")

	args = parser.parse_args()

	train_dataset = PokerImitationDataset(args.train)
	val_dataset = PokerImitationDataset(args.validation)

	if len(train_dataset) == 0:
		raise ValueError("Training dataset is empty.")

	# Infer observation size from first sample
	obs_size = train_dataset[0]["observation"].size(0)

	model = PokerPolicyNetwork(observation_size=obs_size)

	device = "cuda" if torch.cuda.is_available() else "cpu"
	print(f"Using device: {device}")

	trainer = ImitationTrainer(
		model=model,
		train_dataset=train_dataset,
		validation_dataset=val_dataset,
		learning_rate=args.learning_rate,
		batch_size=args.batch_size,
		device=device
	)

	print(f"Starting training for {args.epochs} epochs...")
	history = trainer.train(epochs=args.epochs)

	final_metrics = history[-1]
	print(f"Training finished. Final metrics: {final_metrics}")

	output_path = Path(args.output)
	output_path.parent.mkdir(parents=True, exist_ok=True)
	torch.save(model.state_dict(), output_path)
	print(f"Model saved to {output_path}")

if __name__ == "__main__":
	main()
