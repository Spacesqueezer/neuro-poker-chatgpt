from itertools import combinations

from poker.evaluation.evaluator import evaluate


def evaluate_seven_cards(cards):
	if len(cards) != 7:
		raise ValueError("Texas Hold'em evaluation requires exactly seven cards")

	best_result = None

	for combination in combinations(cards, 5):
		result = evaluate(combination)

		if best_result is None:
			best_result = result
			continue

		if result.rank > best_result.rank:
			best_result = result
		elif result.rank == best_result.rank and result.tiebreaker > best_result.tiebreaker:
			best_result = result

	return best_result
