import random
from math import comb

import pytest

from poker.cards.card import Card
from poker.enums import Rank, Suit
from poker.evaluation.seven_card import evaluate_seven_cards
from poker.hud.odds import DECK, RANKS, category, estimate


def test_category_agrees_with_engine_on_random_seven_card_hands():
    rng = random.Random(44)
    for _ in range(500):
        hand = rng.sample(DECK, 7)
        engine_cards = [Card(Rank(RANKS.index(c[0]) + 2), Suit(c[1].upper())) for c in hand]
        assert category(hand) == int(evaluate_seven_cards(engine_cards).rank)


def test_exact_flush_draw_probabilities():
    flop = estimate(("Ah", "Kh"), ("2h", "7h", "Qc"))
    assert flop["runouts"] == 1081
    p = flop["probabilities"]
    assert p["6"] + p["9"] == pytest.approx(1 - comb(38, 2) / comb(47, 2))
    turn = estimate(("Ah", "Kh"), ("2h", "7h", "Qc", "3s"))
    assert turn["runouts"] == 46
    assert turn["probabilities"]["6"] == pytest.approx(9 / 46)


def test_river_is_a_known_category_not_a_win_probability():
    result = estimate(("As", "Ks"), ("Qs", "Js", "Ts", "2c", "3d"))
    assert result["runouts"] == 1
    assert result["probabilities"]["9"] == 1
    assert result["current_category"] == 9


def test_preflop_is_reproducible_and_normalized():
    a = estimate(("Tc", "3c"), (), samples=1000)
    b = estimate(("3c", "Tc"), (), samples=1000)
    assert a == b and a["method"] == "monte_carlo"
    assert sum(a["probabilities"].values()) == pytest.approx(1)


def test_overall_improvement_counts_only_stronger_categories():
    # Trips on the turn improve on 9 paired-board outs or the remaining ace.
    result = estimate(("As", "Ad"), ("Ac", "Kh", "7s", "2d"))
    assert result["current_category"] == 4
    assert result["improvement_probability"] == pytest.approx(10 / 46)
    assert result["improvement_probability"] == pytest.approx(
        sum(p for rank, p in result["probabilities"].items() if int(rank) > 4)
    )
    river = estimate(("As", "Ad"), ("Ac", "Kh", "7s", "2d", "3h"))
    assert river["improvement_probability"] == 0


@pytest.mark.parametrize(
    "hero,board",
    [
        (("As", "As"), ()),
        (("As", "Kd"), ("As", "2c", "3h")),
        (("As", ""), ()),
        (("As", "Kd"), ("2c",)),
    ],
)
def test_invalid_observations_cannot_generate_probabilities(hero, board):
    with pytest.raises(ValueError):
        estimate(hero, board)
