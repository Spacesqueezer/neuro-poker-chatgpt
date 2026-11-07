"""Deterministic, suit-invariant facts from hero/board cards; never equity or labels."""

from collections import Counter
from functools import lru_cache
from itertools import combinations

from poker.cards.card import Card
from poker.enums import Rank, Suit
from poker.evaluation.evaluator import evaluate
from poker.evaluation.hand_rank import HandRank

RANKS = "23456789TJQKA"
SUITS = "cdhs"
DECK = tuple(r + s for r in RANKS for s in SUITS)
OBJECTS = {
    r + s: Card(Rank(i + 2), suit)
    for i, r in enumerate(RANKS)
    for s, suit in zip(SUITS, (Suit.CLUBS, Suit.DIAMONDS, Suit.HEARTS, Suit.SPADES), strict=True)
}
WINDOWS = (frozenset((14, 2, 3, 4, 5)),) + tuple(
    frozenset(range(high - 4, high + 1)) for high in range(6, 15)
)
CARD_FEATURES = (
    "hole.high_rank",
    "hole.low_rank",
    "hole.rank_gap",
    "hole.pair",
    "hole.suited",
    "made.known",
    *("made." + rank.name.lower() for rank in HandRank),
    *(f"made.tiebreaker_{i}" for i in range(5)),
    "made.min_hole_cards",
    "made.max_hole_cards",
    "board_five.known",
    *("board_five." + rank.name.lower() for rank in HandRank),
    *(f"board_five.tiebreaker_{i}" for i in range(5)),
    "river.improves_board",
    "river.plays_board",
    "texture.board_present",
    "texture.board_high_rank",
    "texture.board_max_multiplicity",
    "texture.board_pairs",
    "texture.board_max_suit_count",
    "texture.board_straight_window",
    "hero.overcards",
    "hero.overpair",
    "hero.top_pair",
    "hero.matching_board_cards",
    "draw.next_card_available",
    "draw.straight_completion",
    "draw.flush_completion",
    "draw.either_completion",
    "draw.straight_improves_board",
    "draw.flush_improves_board",
    "draw.either_improves_board",
)
SEMANTICS = {
    "schema_version": "visible-card-facts/1",
    "made_hand": "best lexicographic rank/tiebreaker over every five-card subset; unknown preflop",
    "hole_usage": "min/max hole-card count among all tied best five-card subsets, divided by 2",
    "board_five": "known only with five board cards; shorter board texture is separate",
    "rank_scale": "rank / 14, hole gap / 12, five tiebreakers padded with zeros",
    "draw_denominator": "52 minus visible distinct cards, on flop/turn only",
    "draw_completion": (
        "unseen next cards making a straight/flush when current best category is lower"
    ),
    "draw_improves_board": "completion with better straight/flush than board plus next card alone",
    "draw_union": "set union, never double-counting straight/flush overlap",
    "draw_limits": (
        "not clean winning outs, not equity; no backdoor or straight-flush draw features"
    ),
    "uses": "hero cards and current board only; no RNG, opponent cards, history or target",
}


def _ranks(cards):
    return [OBJECTS[c].rank.value for c in cards]


def _best(cards):
    best, subsets = None, []
    for five in combinations(cards, 5):
        result = evaluate([OBJECTS[c] for c in five])
        score = (int(result.rank), result.tiebreaker)
        if best is None or score > best:
            best, subsets = score, [five]
        elif score == best:
            subsets.append(five)
    return best, subsets


def _score_vector(score):
    if score is None:
        return (0.0,) * 15
    category, kickers = score
    return (
        1.0,
        *(float(category == rank) for rank in HandRank),
        *(r / 14 for r in kickers),
        *((0.0,) * (5 - len(kickers))),
    )


def _straight_high(cards):
    ranks = set(_ranks(cards))
    return max(
        (high for high, window in zip(range(5, 15), WINDOWS, strict=True) if window <= ranks),
        default=0,
    )


def _flush_value(cards):
    return max(
        (
            tuple(sorted((OBJECTS[c].rank.value for c in cards if c[1] == suit), reverse=True)[:5])
            for suit in SUITS
            if sum(c[1] == suit for c in cards) >= 5
        ),
        default=(),
    )


@lru_cache(maxsize=32768)
def _features(hero, board):
    cards = hero + board
    ranks = sorted(_ranks(hero))
    best, best_subsets = _best(cards)
    board_best, _ = _best(board)
    usage = [sum(c in hero for c in five) for five in best_subsets]
    board_ranks = _ranks(board)
    counts = Counter(board_ranks)
    high = max(board_ranks, default=0)
    board_counts = Counter(c[1] for c in board)
    straight, flush, personal_straight, personal_flush = set(), set(), set(), set()
    draws_available = len(board) in (3, 4)
    if draws_available:
        category = best[0]
        for card in DECK:
            if card in cards:
                continue
            after = cards + (card,)
            next_board = board + (card,)
            if category < HandRank.STRAIGHT and (value := _straight_high(after)):
                straight.add(card)
                if value > _straight_high(next_board):
                    personal_straight.add(card)
            if category < HandRank.FLUSH and (value := _flush_value(after)):
                flush.add(card)
                if value > _flush_value(next_board):
                    personal_flush.add(card)
    denominator = 52 - len(cards)
    result = (
        ranks[1] / 14,
        ranks[0] / 14,
        (ranks[1] - ranks[0]) / 12,
        float(ranks[0] == ranks[1]),
        float(hero[0][1] == hero[1][1]),
        *_score_vector(best),
        min(usage, default=0) / 2,
        max(usage, default=0) / 2,
        *_score_vector(board_best),
        float(board_best is not None and best > board_best),
        float(board_best is not None and best == board_best),
        float(bool(board)),
        high / 14,
        max(counts.values(), default=0) / 4,
        sum(n == 2 for n in counts.values()) / 2,
        max(board_counts.values(), default=0) / 5,
        max(len(set(board_ranks) & window) for window in WINDOWS) / 5,
        sum(r > high for r in ranks) / 2 if board else 0.0,
        float(bool(board) and ranks[0] == ranks[1] and ranks[0] > high),
        float(bool(board) and high in ranks and _ranks(cards).count(high) == 2),
        sum(r in counts for r in ranks) / 2,
        float(draws_available),
        *(
            len(outs) / denominator
            for outs in (
                straight,
                flush,
                straight | flush,
                personal_straight,
                personal_flush,
                personal_straight | personal_flush,
            )
        ),
    )
    assert len(result) == len(CARD_FEATURES)
    return result


def card_features(hero, board):
    """Current deterministic facts; unknown made hand on preflop is explicitly masked."""
    if len(hero) != 2 or len(board) not in (0, 3, 4, 5):
        raise ValueError("Expected two hero cards and a complete current street board")
    cards = tuple(hero) + tuple(board)
    if any(type(c) is not str or c not in OBJECTS for c in cards) or len(set(cards)) != len(cards):
        raise ValueError("Invalid or duplicate visible cards")
    return _features(tuple(sorted(hero)), tuple(sorted(board)))
