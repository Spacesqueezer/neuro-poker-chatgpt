from poker.evaluation.evaluation_result import EvaluationResult


def compare_hands(first: EvaluationResult, second: EvaluationResult):
	if first.rank > second.rank:
		return 1

	if first.rank < second.rank:
		return -1

	if first.tiebreaker > second.tiebreaker:
		return 1

	if first.tiebreaker < second.tiebreaker:
		return -1

	return 0
