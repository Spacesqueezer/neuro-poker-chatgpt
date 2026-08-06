from dataclasses import dataclass

from poker.enums import Rank, Suit


@dataclass(frozen=True)
class Card:
	rank: Rank
	suit: Suit

	def __str__(self):
		return f"{self.rank.name}_{self.suit.value}"
