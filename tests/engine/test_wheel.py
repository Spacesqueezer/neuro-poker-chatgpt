import pytest

from poker.cards.card import Card
from poker.enums import Rank, Suit
from poker.evaluation.evaluator import evaluate
from poker.evaluation.hand_rank import HandRank


@pytest.mark.parametrize("flush", [False, True])
def test_wheel_is_five_high_and_loses_to_six_high(flush):
    def hand(ranks):
        return [
            Card(Rank(rank), Suit.SPADES if flush or i % 2 else Suit.HEARTS)
            for i, rank in enumerate(ranks)
        ]

    wheel = evaluate(hand([14, 2, 3, 4, 5]))
    six = evaluate(hand([2, 3, 4, 5, 6]))
    assert wheel.rank == (HandRank.STRAIGHT_FLUSH if flush else HandRank.STRAIGHT)
    assert wheel.rank == six.rank
    assert wheel.tiebreaker == (5,)
    assert wheel.tiebreaker < six.tiebreaker


def test_ace_cannot_wrap_in_the_middle_of_a_straight():
    cards = [
        Card(Rank(rank), Suit.SPADES if i % 2 else Suit.HEARTS)
        for i, rank in enumerate([12, 13, 14, 2, 3])
    ]
    assert evaluate(cards).rank == HandRank.HIGH_CARD
