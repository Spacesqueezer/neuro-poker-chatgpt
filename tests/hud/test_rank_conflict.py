from pathlib import Path

import cv2
import numpy as np
import pytest

from poker.hud import cards
from poker.hud.recognition import configure_ocr


@pytest.mark.parametrize(
    "number,hero,board",
    [
        (551, ("Ah", "Kc"), ("8s", "5h", "9d")),
        (555, ("Ah", "Kc"), ("8s", "5h", "9d")),
        (1080, ("Jc", "Th"), ("5c", "4s", "5s", "Qs")),
        (1781, ("9d", "4c"), ("7d", "8c", "Th", "5h")),
    ],
)
def test_small_lossless_cards_under_tooltips(number, hero, board):
    from poker.hud.hand import observe

    path = Path(__file__).resolve().parents[2] / (
        f"artifacts/hud/sessions/session_20260914_083437_99b85d/requests/{number:08d}.png"
    )
    if not path.exists():
        pytest.skip("Local diagnostic frame unavailable")
    configure_ocr()
    hand = observe(cards.find_cards(cv2.imread(str(path))))
    assert (hand.hero, hand.board, hand.valid) == (hero, board, True)


@pytest.mark.parametrize(
    "second,large,expected",
    [
        (("9", 28), ("", 0), "9"),
        (("8", 28), ("", 0), ""),
        (("9", 24), ("", 0), ""),
        (("9", 28), ("3", 95), ""),
    ],
)
def test_weak_corner_needs_two_readings_and_shape_without_strong_conflict(
    monkeypatch, second, large, expected
):
    readings = iter([("9", 41), second, ("", 0), large, ("", 0)])
    monkeypatch.setattr(cards, "rank_candidate", lambda *args: next(readings))
    monkeypatch.setattr(cards, "segmented_rank", lambda *args: ("", 0))
    monkeypatch.setattr(
        cards, "match_rank_shape", lambda *args, **kwargs: ("9", 86.8) if kwargs else ("", 0)
    )
    assert cards.read_rank(np.zeros((122, 86, 3), np.uint8))[0] == expected


def test_nine_with_chips_covering_the_large_glyph():
    path = (
        Path(__file__).resolve().parents[2]
        / "artifacts/hud/sessions/session_20260913_161745_1e250e/frames/00002788.jpg"
    )
    if not path.exists():
        pytest.skip("Local diagnostic frame unavailable")
    configure_ocr()
    assert "9c" in {c.value for c in cards.find_cards(cv2.imread(str(path))) if c.zone == "board"}


@pytest.mark.parametrize(
    "covered,corner,expected", [(True, 94, "9"), (False, 94, ""), (True, 89, "")]
)
def test_occluded_large_glyph_requires_strong_corner(monkeypatch, covered, corner, expected):
    image = np.zeros((146, 102, 3), np.uint8)
    if covered:
        image[115:, 40:] = (220, 100, 0)
    readings = iter([("9", corner), ("3", 95)])
    monkeypatch.setattr(cards, "rank_candidate", lambda *args: next(readings))
    monkeypatch.setattr(cards, "segmented_rank", lambda *args: ("", 0))
    monkeypatch.setattr(cards, "match_rank_shape", lambda *args: ("", 0))
    assert cards.read_rank(image)[0] == expected


@pytest.mark.parametrize("number", [2296, 2321, 2328])
def test_ten_on_lossless_small_window_frames(number):
    path = (
        Path(__file__).resolve().parents[2]
        / f"artifacts/hud/sessions/session_20260913_161745_1e250e/requests/{number:08d}.png"
    )
    if not path.exists():
        pytest.skip("Local lossless diagnostic frame unavailable")
    configure_ocr()
    found = cards.find_cards(cv2.imread(str(path)))
    ten = next(c for c in found if c.zone == "board" and c.value == "Ts")
    assert ten.rank_confidence >= 85


@pytest.mark.parametrize("segmented,score,expected", [("T", 86, 86), ("T", 84, 73), ("9", 86, 73)])
def test_segmented_rank_only_strengthens_matching_reading(monkeypatch, segmented, score, expected):
    monkeypatch.setattr(cards, "rank_candidate", lambda *args: ("T", 73))
    monkeypatch.setattr(cards, "segmented_rank", lambda *args: (segmented, score))
    monkeypatch.setattr(cards, "match_rank_shape", lambda *args: ("", 0))
    assert cards.read_rank(np.zeros((122, 85, 3), np.uint8)) == ("T", expected)


@pytest.mark.parametrize("number", [1019, 1023, 1038])
def test_chip_distorted_nine(number):
    root = Path(__file__).resolve().parents[2]
    path = root / f"artifacts/hud/sessions/session_20260912_074919_b1e521/frames/{number:08d}.jpg"
    if not path.exists():
        pytest.skip("Local recorded session unavailable")
    configure_ocr()
    found = cards.find_cards(cv2.imread(str(path)))
    assert "9s" in {c.value for c in found if c.zone == "board"}


@pytest.mark.parametrize(
    "large_score,shape_score,expected", [(86, 95.2, "9"), (95, 95.2, ""), (86, 94.9, "")]
)
def test_conflicting_large_rank_needs_strict_shape_match(
    monkeypatch, large_score, shape_score, expected
):
    readings = iter([("", 0), ("9", 53), ("9", 17), ("3", 49), ("3", large_score)])
    monkeypatch.setattr(cards, "rank_candidate", lambda *args: next(readings))
    monkeypatch.setattr(cards, "segmented_rank", lambda *args: ("9", 0))
    monkeypatch.setattr(cards, "match_rank_shape", lambda *args: ("9", shape_score))
    assert cards.read_rank(np.zeros((151, 103, 3), np.uint8))[0] == expected


@pytest.mark.parametrize("number", [2677, 2679])
def test_hand_tooltip_does_not_merge_hero_card(number):
    root = Path(__file__).resolve().parents[2]
    path = root / f"artifacts/hud/sessions/session_20260912_114052_d37ed0/frames/{number:08d}.jpg"
    if not path.exists():
        pytest.skip("Local recorded session unavailable")
    configure_ocr()
    found = cards.find_cards(cv2.imread(str(path)))
    assert [c.value for c in found if c.zone == "hero"] == ["5d", "3d"]


@pytest.mark.parametrize("number", [4781, 4822])
def test_avatar_highlight_is_not_an_extra_card(number):
    root = Path(__file__).resolve().parents[2]
    path = root / f"artifacts/hud/sessions/session_20260912_114052_d37ed0/frames/{number:08d}.jpg"
    if not path.exists():
        pytest.skip("Local recorded session unavailable")
    configure_ocr()
    found = cards.find_cards(cv2.imread(str(path)))
    assert [c.value for c in found if c.zone == "hero"] == ["7c", "4c"]


@pytest.mark.parametrize("number,expected", [(1580, ["Kd", "Js"]), (2280, ["7c", "5c"])])
def test_tooltip_joining_both_cards(number, expected):
    root = Path(__file__).resolve().parents[2]
    path = root / f"artifacts/hud/sessions/session_20260912_114052_d37ed0/frames/{number:08d}.jpg"
    if not path.exists():
        pytest.skip("Local recorded session unavailable")
    configure_ocr()
    found = cards.find_cards(cv2.imread(str(path)))
    assert [c.value for c in found if c.zone == "hero"] == expected
