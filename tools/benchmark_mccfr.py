import argparse
import json
import time
from pathlib import Path

from poker.cards.card import Card
from poker.enums import Rank, Suit
from poker.solver import (
	ExternalSamplingMCCFR,
	HeadsUpHoldemDeal,
	HoldemActionAbstraction,
	RestrictedHeadsUpHoldemGame,
)


BENCHMARK_SCENARIOS = {
	"equal": (20, 20),
	"asymmetric": (8, 20),
}


def create_benchmark_game(scenario="equal"):
	deal = HeadsUpHoldemDeal(
		hole_cards=(
			(
				Card(Rank.ACE, Suit.SPADES),
				Card(Rank.ACE, Suit.HEARTS),
			),
			(
				Card(Rank.KING, Suit.SPADES),
				Card(Rank.KING, Suit.HEARTS),
			),
		),
		board=(
			Card(Rank.TWO, Suit.CLUBS),
			Card(Rank.THREE, Suit.DIAMONDS),
			Card(Rank.FOUR, Suit.HEARTS),
			Card(Rank.FIVE, Suit.CLUBS),
			Card(Rank.SEVEN, Suit.SPADES),
		),
	)

	try:
		starting_stacks = BENCHMARK_SCENARIOS[scenario]
	except KeyError as error:
		raise ValueError(
			f"unknown benchmark scenario: {scenario}"
		) from error

	return RestrictedHeadsUpHoldemGame(
		(deal,),
		starting_stacks=starting_stacks,
		action_abstraction=HoldemActionAbstraction(
			postflop_bet_sizes_bb=(1, 2),
			postflop_raise_increment_multiplier=2,
		),
	)


def strategy_distance(first, second):
	keys = set(first) | set(second)
	if not keys:
		return 0.0

	total = 0.0
	count = 0

	for key in keys:
		first_strategy = first.get(key, {})
		second_strategy = second.get(key, {})
		actions = set(first_strategy) | set(second_strategy)

		for action in actions:
			total += abs(
				first_strategy.get(action, 0.0)
				- second_strategy.get(action, 0.0)
			)
			count += 1

	return total / count if count else 0.0


def run_benchmark(iterations, seed, scenario="equal"):
	if iterations <= 1:
		raise ValueError("iterations must be greater than 1")

	game = create_benchmark_game(scenario)
	first_iterations = max(1, iterations // 2)

	started = time.perf_counter()
	first = ExternalSamplingMCCFR(
		game,
		seed=seed,
	).train(first_iterations)
	first_seconds = time.perf_counter() - started

	started = time.perf_counter()
	final = ExternalSamplingMCCFR(
		game,
		seed=seed,
	).train(iterations)
	final_seconds = time.perf_counter() - started

	return {
		"benchmark_version": 2,
		"scenario": scenario,
		"starting_stacks": list(game.starting_stacks),
		"iterations": iterations,
		"seed": seed,
		"first_checkpoint_iterations": first_iterations,
		"information_sets": len(final.average_strategy),
		"strategy_distance_from_first_checkpoint": strategy_distance(
			first.average_strategy,
			final.average_strategy,
		),
		"first_checkpoint_seconds": round(first_seconds, 6),
		"final_seconds": round(final_seconds, 6),
		"final_iterations_per_second": round(
			iterations / final_seconds,
			6,
		) if final_seconds > 0.0 else None,
	}


def write_report(report, output):
	path = Path(output)
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(
		json.dumps(report, indent=2) + "\n",
		encoding="utf-8",
	)


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("--iterations", type=int, default=100)
	parser.add_argument("--seed", type=int, default=42)
	parser.add_argument(
		"--scenario",
		choices=tuple(BENCHMARK_SCENARIOS),
		default="equal",
	)
	parser.add_argument("--output")
	args = parser.parse_args()

	report = run_benchmark(
		args.iterations,
		args.seed,
		args.scenario,
	)
	if args.output:
		write_report(report, args.output)

	print(
		json.dumps(
			report,
			indent=2,
		)
	)


if __name__ == "__main__":
	main()
