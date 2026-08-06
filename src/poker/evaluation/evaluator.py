from collections import Counter

from poker.evaluation.evaluation_result import EvaluationResult
from poker.evaluation.hand_rank import HandRank


def evaluate(cards):
	if len(cards) < 5:
		raise ValueError("At least five cards are required")

	ranks = [card.rank.value for card in cards]
	counts = Counter(ranks)

	if 4 in counts.values():
		rank = HandRank.FOUR_OF_A_KIND
	elif 3 in counts.values() and 2 in counts.values():
		rank = HandRank.FULL_HOUSE
	elif 3 in counts.values():
		rank = HandRank.THREE_OF_A_KIND
	elif list(counts.values()).count(2) == 2:
		rank = HandRank.TWO_PAIR
	elif 2 in counts.values():
		rank = HandRank.PAIR
	else:
		rank = HandRank.HIGH_CARD

	return EvaluationResult(
		rank=rank,
		cards=tuple(cards)
	)
