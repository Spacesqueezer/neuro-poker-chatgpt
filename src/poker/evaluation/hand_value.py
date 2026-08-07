from collections import Counter

from poker.evaluation.hand_rank import HandRank


def build_tiebreaker(cards, rank):
	ranks = [card.rank.value for card in cards]
	counts = Counter(ranks)

	if rank == HandRank.FOUR_OF_A_KIND:
		quad = max(value for value, count in counts.items() if count == 4)
		kicker = max(value for value, count in counts.items() if count == 1)
		return (quad, kicker)

	if rank == HandRank.FULL_HOUSE:
		trips = max(value for value, count in counts.items() if count == 3)
		pair = max(value for value, count in counts.items() if count == 2)
		return (trips, pair)

	if rank == HandRank.THREE_OF_A_KIND:
		trips = max(value for value, count in counts.items() if count == 3)
		kickers = sorted(
			[value for value, count in counts.items() if count == 1],
			reverse=True,
		)
		return (trips, *kickers)

	if rank == HandRank.TWO_PAIR:
		pairs = sorted(
			[value for value, count in counts.items() if count == 2],
			reverse=True,
		)
		kicker = max(value for value, count in counts.items() if count == 1)
		return (*pairs, kicker)

	if rank == HandRank.PAIR:
		pair = max(value for value, count in counts.items() if count == 2)
		kickers = sorted(
			[value for value, count in counts.items() if count == 1],
			reverse=True,
		)
		return (pair, *kickers)

	return tuple(sorted(ranks, reverse=True))
