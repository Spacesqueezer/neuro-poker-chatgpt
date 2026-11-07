import random
from itertools import combinations, permutations

import pytest

from poker.evaluation.evaluator import evaluate
from poker.evaluation.hand_rank import HandRank
from poker.learning.snapshot_card_features import CARD_FEATURES, DECK, OBJECTS, card_features


def facts(hero, board):
    return dict(zip(CARD_FEATURES, card_features(hero.split(), board.split()), strict=True))


@pytest.mark.parametrize(
    "hero,board,category,high",
    [
        ("6h Jc", "2s 3s Qd 5c 4c", "straight", 6),
        ("5s 9s", "3d 7s 6c 8d", "straight", 9),
        ("Jd Qc", "Kc 8h Td 6d 9d", "straight", 13),
        ("Tc 6d", "6s 7d 6h", "three_of_a_kind", 6),
        ("Tc 6d", "6s 7d 6h Td", "full_house", 6),
        ("8c Tc", "Jc 9c 5s 7h", "straight", 11),
        ("6h Th", "4h 7c Kc Kh Ah", "flush", 14),
        ("Kh Qh", "9h 6h Ah", "flush", 14),
        ("Ah 2d", "3c 4s 5d", "straight", 5),
        ("Ac Ad", "Ah Kc Kd Kh Qs", "full_house", 14),
        ("8h 9h", "Th Jh Qh 2c 2d", "straight_flush", 12),
    ],
)
def test_known_hands_and_previously_missed_strong_hands(hero, board, category, high):
    row = facts(hero, board)
    assert row["made.known"] == 1 and row["made." + category] == 1
    assert sum(row["made." + r.name.lower()] for r in HandRank) == 1
    assert row["made.tiebreaker_0"] == high / 14


def test_preflop_masks_unknown_five_card_hand_and_preserves_hole_structure():
    row = facts("As Ah", "")
    assert row["hole.pair"] == 1 and row["hole.high_rank"] == 1
    assert row["hole.low_rank"] == 1 and row["hole.rank_gap"] == 0
    assert all(value == 0 for name, value in row.items() if not name.startswith("hole."))
    row = facts("Ah 2h", "")
    assert row["hole.suited"] == 1 and row["hole.rank_gap"] == 1


def test_board_only_hand_kicker_improvement_and_all_tied_best_subsets():
    royal = facts("2c 3d", "Ah Kh Qh Jh Th")
    assert royal["river.plays_board"] == royal["board_five.straight_flush"] == 1
    assert royal["river.improves_board"] == royal["made.max_hole_cards"] == 0
    same = facts("As Kd", "Ah Kc Qc Jd Tc")
    assert same["river.plays_board"] == 1
    assert same["made.min_hole_cards"] == 0 and same["made.max_hole_cards"] == 1
    kicker = facts("Kc 3s", "As Ah Ac Ad 2d")
    assert kicker["made.four_of_a_kind"] == kicker["river.improves_board"] == 1
    assert kicker["made.tiebreaker_1"] == 13 / 14
    assert kicker["made.min_hole_cards"] == kicker["made.max_hole_cards"] == 0.5
    pair_upgrade = facts("Ac Ad", "2c 2d 2h 3s 3d")
    assert pair_upgrade["made.full_house"] == pair_upgrade["board_five.full_house"] == 1
    assert pair_upgrade["river.improves_board"] == 1
    assert pair_upgrade["made.tiebreaker_1"] == 1


def test_paired_board_is_distinct_from_hero_pair_and_short_board_is_not_five_cards():
    paired = facts("Ah Kd", "7c 7s Qh")
    assert paired["made.pair"] == 1 and paired["made.tiebreaker_0"] == 7 / 14
    assert paired["hero.matching_board_cards"] == paired["hero.top_pair"] == 0
    assert paired["texture.board_pairs"] == 0.5 and paired["hero.overcards"] == 1
    assert all(v == 0 for k, v in paired.items() if k.startswith("board_five."))
    assert facts("Ah Qd", "Qh 2d 3s")["hero.top_pair"] == 1
    assert facts("Ah Ad", "Qh 2d 3s")["hero.overpair"] == 1
    assert facts("Ah Qd", "Qh Qc 3s")["hero.top_pair"] == 0  # Trips, not top pair.


def test_draws_deduplicate_overlap_and_handle_wheel_and_double_gutshot():
    combo = facts("8h 9h", "6h 7h Qc")
    assert combo["draw.straight_completion"] == 8 / 47
    assert combo["draw.flush_completion"] == 9 / 47
    assert combo["draw.either_completion"] == 15 / 47  # Two overlapping heart outs.
    assert combo["draw.either_improves_board"] == 15 / 47
    assert facts("Ah 2d", "3c 4s 9h")["draw.straight_completion"] == 4 / 47
    assert facts("8h 9d", "5c 7s Jh")["draw.straight_completion"] == 8 / 47


def test_shared_board_draws_are_not_hero_improvements_and_river_has_no_draws():
    shared = facts("2c 3d", "7h 8h 9h Th")
    assert shared["draw.straight_completion"] == 8 / 46
    assert shared["draw.flush_completion"] == 9 / 46
    assert shared["draw.either_completion"] == 15 / 46
    assert shared["draw.either_improves_board"] == 0
    personal = facts("Ah 2c", "7h 8h 9h Td")
    assert personal["draw.flush_improves_board"] == personal["draw.flush_completion"] == 9 / 46
    river = facts("8h 9h", "6h 7h Qc 2d 3s")
    assert all(v == 0 for k, v in river.items() if k.startswith("draw."))
    made = facts("Ah Kh", "Qh Jh Th")
    assert made["draw.next_card_available"] == 1 and made["draw.either_completion"] == 0


def test_all_suit_bijections_and_card_orders_preserve_every_fact_and_randomness():
    hero, board = ["8h", "9h"], ["6h", "7h", "Qc", "2d"]
    original = card_features(hero, board)
    rng = random.getstate()
    for perm in permutations("cdhs"):
        translation = dict(zip("cdhs", perm, strict=True))

        def mapped(cards, translation=translation):
            return [c[0] + translation[c[1]] for c in reversed(cards)]

        assert card_features(mapped(hero), mapped(board)) == original
    assert random.getstate() == rng
    assert all(0 <= value <= 1 for value in original)


@pytest.mark.parametrize(
    "hero,board",
    [
        (["Ah"], []),
        (["Ah", "Ah"], []),
        (["Ah", "Kd"], ["Ah", "2c", "3s"]),
        (["AH", "Kd"], []),
        (["Ah", "Kd"], ["2c"]),
        ([{}, "Kd"], []),
    ],
)
def test_malformed_card_data_is_rejected(hero, board):
    with pytest.raises(ValueError):
        card_features(hero, board)


def test_draw_features_match_enumeration_of_real_five_card_combinations():
    rng = random.Random(1761)
    for board_size in (3, 4):
        for _ in range(5):
            cards = rng.sample(DECK, board_size + 2)
            hero, board = cards[:2], cards[2:]
            row = dict(zip(CARD_FEATURES, card_features(hero, board), strict=True))
            current = max(
                evaluate([OBJECTS[c] for c in five]).rank for five in combinations(cards, 5)
            )
            straight, flush = set(), set()
            for card in set(DECK) - set(cards):
                kinds = {
                    evaluate([OBJECTS[c] for c in five]).rank
                    for five in combinations([*cards, card], 5)
                }
                if current < HandRank.STRAIGHT and kinds & {
                    HandRank.STRAIGHT,
                    HandRank.STRAIGHT_FLUSH,
                }:
                    straight.add(card)
                if current < HandRank.FLUSH and kinds & {HandRank.FLUSH, HandRank.STRAIGHT_FLUSH}:
                    flush.add(card)
            assert row["draw.straight_completion"] == len(straight) / (52 - len(cards))
            assert row["draw.flush_completion"] == len(flush) / (52 - len(cards))
            assert row["draw.either_completion"] == len(straight | flush) / (52 - len(cards))
