from collections import Counter

from poker.evaluation.evaluation_result import EvaluationResult
from poker.evaluation.hand_rank import HandRank
from poker.evaluation.hand_value import build_tiebreaker


def has_straight(ranks):
	unique = sorted(set(ranks))

	if len(unique) != 5:
		return False

	return unique[-1] - unique[0] == 4


def has_flush(cards):
	return len({card.suit for card in cards}) == 1


def evaluate(cards):
	if len(cards) < 5:
		raise ValueError("At least five cards are required")

	ranks = [card.rank.value for card in cards]
	counts = Counter(ranks)

	if has_straight(ranks) and has_flush(cards):
		rank = HandRank.STRAIGHT_FLUSH
	elif 4 in counts.values():
		rank = HandRank.FOUR_OF_A_KIND
	elif 3 in counts.values() and 2 in counts.values():
		rank = HandRank.FULL_HOUSE
	elif has_flush(cards):
		rank = HandRank.FLUSH
	elif has_straight(ranks):
		rank = HandRank.STRAIGHT
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
		cards=tuple(cards),
		tiebreaker=build_tiebreaker(cards, rank)
	)
