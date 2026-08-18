import argparse
import json

from poker.arena.benchmark import (
	ExpertBenchmarkConfig,
	ExpertBenchmarkRunner,
)


def main():
	parser = argparse.ArgumentParser(
		description="Benchmark ExpertAgent against baseline opponents.",
	)
	parser.add_argument("--sessions", type=int, default=20)
	parser.add_argument("--hands-per-session", type=int, default=100)
	parser.add_argument("--starting-stack", type=int, default=200)
	parser.add_argument("--seed", type=int, default=42)
	parser.add_argument("--equity-samples", type=int, default=300)
	parser.add_argument(
		"--opponents",
		nargs="+",
		default=["random", "calling_station", "nit", "maniac", "tag", "lag"],
		choices=["random", "calling_station", "nit", "maniac", "tag", "lag"],
	)
	parser.add_argument("--output")
	args = parser.parse_args()

	config = ExpertBenchmarkConfig(
		sessions=args.sessions,
		hands_per_session=args.hands_per_session,
		starting_stack=args.starting_stack,
		seed=args.seed,
		equity_samples=args.equity_samples,
		opponents=tuple(args.opponents),
	)
	result = ExpertBenchmarkRunner().run(config)
	payload = result.to_dict()
	text = json.dumps(
		payload,
		indent=2,
		ensure_ascii=False,
	)

	if args.output:
		with open(args.output, "w", encoding="utf-8") as file:
			file.write(text)
			file.write("\n")

	print(text)


if __name__ == "__main__":
	main()
