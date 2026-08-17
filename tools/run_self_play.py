import argparse
import json
from pathlib import Path

from poker.agents.neural import NeuralAgent
from poker.arena.runner import ArenaRunner
from poker.learning.dataset import LearningDatasetWriter
from poker.learning.rl_dataset import RLDatasetCapture
from poker.learning.self_play import ModelPool

def main():
	parser = argparse.ArgumentParser(description="Run Self-Play data generation using RLDatasetCapture")
	parser.add_argument("--current-model", required=True, help="Path to the current neural model weights (.pt)")
	parser.add_argument("--pool-dir", required=True, help="Directory containing historical models")
	parser.add_argument("--output", required=True, help="Path to output JSONL dataset")
	parser.add_argument("--hands", type=int, default=1000, help="Number of hands to play")
	parser.add_argument("--seed", type=int, default=42, help="Random seed")
	parser.add_argument("--starting-stack", type=int, default=200, help="Starting stack for each player")

	args = parser.parse_args()

	pool = ModelPool(args.pool_dir)
	historical_model_path = pool.sample_model(seed=args.seed)

	current_agent = NeuralAgent(model_path=args.current_model, stochastic=True)

	if historical_model_path is None:
		print("No historical models found. Using current model for both players.")
		opponent_agent = NeuralAgent(model_path=args.current_model, stochastic=True)
		historical_model_path = args.current_model
	else:
		print(f"Sampled historical model: {historical_model_path.name}")
		opponent_agent = NeuralAgent(model_path=str(historical_model_path), stochastic=True)

	agents = {
		"current": current_agent,
		"historical": opponent_agent
	}

	output_path = Path(args.output)
	if output_path.exists():
		output_path.unlink()

	writer = LearningDatasetWriter(output_path)

	capture = RLDatasetCapture(
		writer=writer,
		include_players=["current", "historical"]
	)

	runner = ArenaRunner(
		agents=agents,
		starting_stack=args.starting_stack,
		decision_observer=capture.decision_observer,
		hand_observer=capture.hand_observer
	)

	print(f"Starting Self-Play Arena for {args.hands} hands...")
	stats = runner.run(hands=args.hands, seed=args.seed)

	print(json.dumps({
		"hands_played": stats.hands,
		"failed_hands": stats.failed_hands,
		"current_model": args.current_model,
		"historical_model": str(historical_model_path),
		"output": args.output,
	}, indent=2))


if __name__ == "__main__":
	main()
