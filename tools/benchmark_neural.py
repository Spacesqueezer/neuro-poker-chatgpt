import argparse
import json
from pathlib import Path

from poker.agents import CallingStationAgent, NitAgent, RandomAgent, NeuralAgent, ManiacAgent, TAGAgent, LAGAgent
from poker.arena.runner import ArenaRunner


def main():
	parser = argparse.ArgumentParser(description="Benchmark NeuralAgent against baselines")
	parser.add_argument("--model", required=True, help="Path to NeuralAgent .pt weights")
	parser.add_argument("--opponents", nargs="+", choices=["random", "calling_station", "nit", "maniac", "tag", "lag"], default=["random"])
	parser.add_argument("--hands", type=int, default=1000)
	parser.add_argument("--seed", type=int, default=42)
	parser.add_argument("--starting-stack", type=int, default=200)
	parser.add_argument("--output", type=str)
	args = parser.parse_args()

	neural_agent = NeuralAgent(model_path=args.model, agent_id="benchmark_agent")

	results = []

	for opponent_name in args.opponents:
		print(f"Benchmarking against {opponent_name} for {args.hands} hands...")

		if opponent_name == "random":
			opponent = RandomAgent(seed=args.seed)
		elif opponent_name == "calling_station":
			opponent = CallingStationAgent()
		elif opponent_name == "nit":
			opponent = NitAgent()
		elif opponent_name == "maniac":
			opponent = ManiacAgent(seed=args.seed)
		elif opponent_name == "tag":
			opponent = TAGAgent(seed=args.seed)
		elif opponent_name == "lag":
			opponent = LAGAgent(seed=args.seed)

		agents = {
			"neural": neural_agent,
			opponent_name: opponent
		}

		runner = ArenaRunner(agents, starting_stack=args.starting_stack)
		stats = runner.run(hands=args.hands, seed=args.seed)

		# Simplistic evaluation
		neural_profit = sum(stats.player_profit.get("neural", []))

		results.append({
			"opponent": opponent_name,
			"hands": stats.hands,
			"failed_hands": stats.failed_hands,
			"neural_profit": neural_profit,
			"bb_per_100": (neural_profit / 2) / (stats.hands / 100) if stats.hands > 0 else 0,
		})

	print("\nBenchmark Results:")
	print(json.dumps(results, indent=2))

	if args.output:
		output_path = Path(args.output)
		output_path.parent.mkdir(parents=True, exist_ok=True)
		output_path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
		print(f"Results saved to {output_path}")


if __name__ == "__main__":
	main()
