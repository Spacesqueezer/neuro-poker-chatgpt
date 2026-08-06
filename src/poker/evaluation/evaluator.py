from dataclasses import dataclass

from poker.cards.card import Card
from poker.evaluation.hand_rank import HandRank


@dataclass(frozen=True)
class EvaluationResult:
	rank: HandRank
	cards: tuple[Card, ...]


def evaluate(cards):
	if len(cards) < 5:
		raise ValueError("At least five cards are required")

	return EvaluationResult(
		rank=HandRank.HIGH_CARD,
		cards=tuple(cards)
	)
