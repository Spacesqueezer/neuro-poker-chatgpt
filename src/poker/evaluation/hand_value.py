from collections import Counter


def build_tiebreaker(cards, rank):
	ranks = [card.rank.value for card in cards]
	counts = Counter(ranks)

	if rank.name == "FOUR_OF_A_KIND":
		quad = max(value for value, count in counts.items() if count == 4)
		kicker = max(value for value, count in counts.items() if count == 1)
		return (quad, kicker)

	if rank.name == "FULL_HOUSE":
		trips = max(value for value, count in counts.items() if count == 3)
		pair = max(value for value, count in counts.items() if count == 2)
		return (trips, pair)

	ordered = sorted(ranks, reverse=True)
	return tuple(ordered)
