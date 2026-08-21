from dataclasses import dataclass

from poker.enums import Rank, Suit

SUIT_SYMBOLS = {
	Suit.CLUBS: "♣",
	Suit.DIAMONDS: "♦",
	Suit.HEARTS: "♥",
	Suit.SPADES: "♠",
}


RANK_SYMBOLS = {
	Rank.JACK: "J",
	Rank.QUEEN: "Q",
	Rank.KING: "K",
	Rank.ACE: "A",
}


@dataclass(frozen=True)
class Card:
	rank: Rank
	suit: Suit

	def __str__(self):
		rank = RANK_SYMBOLS.get(self.rank, str(self.rank.value))
		return f"{rank}{SUIT_SYMBOLS[self.suit]}"
