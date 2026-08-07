from poker.evaluation.comparator import compare_hands
from poker.evaluation.evaluation_result import EvaluationResult
from poker.evaluation.hand_rank import HandRank


def test_stronger_rank_wins():
	first = EvaluationResult(
		rank=HandRank.PAIR,
		cards=(),
	)

	second = EvaluationResult(
		rank=HandRank.HIGH_CARD,
		cards=(),
	)

	assert compare_hands(first, second) == 1


def test_kicker_wins_when_rank_equal():
	first = EvaluationResult(
		rank=HandRank.PAIR,
		cards=(),
		tiebreaker=(14, 13),
	)

	second = EvaluationResult(
		rank=HandRank.PAIR,
		cards=(),
		tiebreaker=(14, 12),
	)

	assert compare_hands(first, second) == 1


def test_evaluation_result_can_compare_real_kickers():
	first = EvaluationResult(
		rank=HandRank.HIGH_CARD,
		cards=(),
		tiebreaker=(14, 13, 10),
	)

	second = EvaluationResult(
		rank=HandRank.HIGH_CARD,
		cards=(),
		tiebreaker=(14, 12, 10),
	)

	assert compare_hands(first, second) == 1
