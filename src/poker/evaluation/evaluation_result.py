from dataclasses import dataclass

from poker.cards.card import Card
from poker.evaluation.hand_rank import HandRank


@dataclass(frozen=True)
class EvaluationResult:
	rank: HandRank
	cards: tuple[Card, ...]
