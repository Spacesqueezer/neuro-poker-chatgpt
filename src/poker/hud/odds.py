"""Distribution of the final best hand, not equity against opponents."""

import hashlib
import random
from collections import Counter
from functools import lru_cache
from itertools import combinations

RANKS = "23456789TJQKA"
SUITS = "shdc"
CATEGORIES = {
    1: "Старшая карта",
    2: "Пара",
    3: "Две пары",
    4: "Сет/тройка",
    5: "Стрит",
    6: "Флеш",
    7: "Фулл-хаус",
    8: "Каре",
    9: "Стрит-флеш",
}
DECK = tuple(rank + suit for rank in RANKS for suit in SUITS)


def straight(ranks):
    values = set(ranks)
    if 14 in values:
        values.add(1)
    return any(all(n in values for n in range(high - 4, high + 1)) for high in range(5, 15))


def category(cards):
    """Only the best category is needed; no opponent or tiebreaker is inferred."""
    ranks = [RANKS.index(card[0]) + 2 for card in cards]
    counts = sorted(Counter(ranks).values(), reverse=True)
    flush_ranks = [
        ranks[i]
        for suit in SUITS
        if sum(card[1] == suit for card in cards) >= 5
        for i, card in enumerate(cards)
        if card[1] == suit
    ]
    if flush_ranks and straight(flush_ranks):
        return 9
    if counts[0] == 4:
        return 8
    if counts[0] >= 3 and len(counts) > 1 and counts[1] >= 2:
        return 7
    if flush_ranks:
        return 6
    if straight(ranks):
        return 5
    if counts[0] == 3:
        return 4
    if counts.count(2) >= 2:
        return 3
    if counts[0] == 2:
        return 2
    return 1


def validate(hero, board):
    cards = tuple(hero) + tuple(board)
    if len(hero) != 2 or len(board) not in (0, 3, 4, 5):
        raise ValueError("Need two hero cards and 0/3/4/5 board cards")
    if any(card not in DECK for card in cards) or len(set(cards)) != len(cards):
        raise ValueError("Unknown or duplicate card")


def estimate(hero, board, samples=6000):
    hero, board = tuple(sorted(hero)), tuple(sorted(board))
    validate(hero, board)
    if samples <= 0:
        raise ValueError("samples must be positive")
    return _estimate(hero, board, samples)


@lru_cache(maxsize=128)
def _estimate(hero, board, samples):
    known = hero + board
    remaining = tuple(card for card in DECK if card not in known)
    missing = 5 - len(board)
    method = "exact" if missing <= 2 else "monte_carlo"
    if method == "exact":
        runouts = combinations(remaining, missing)
    else:
        seed = int.from_bytes(hashlib.sha256("".join(known).encode()).digest()[:8], "big")
        rng = random.Random(seed)
        runouts = (rng.sample(remaining, missing) for _ in range(samples))
    counts = Counter(category(known + tuple(runout)) for runout in runouts)
    count = sum(counts.values())
    current = category(known)
    return {
        "method": method,
        "runouts": count,
        "current_category": current,
        "improvement_probability": sum(n for rank, n in counts.items() if rank > current) / count,
        "improvement_definition": "higher_category_by_river",
        "probabilities": {str(rank): counts[rank] / count for rank in CATEGORIES},
    }
