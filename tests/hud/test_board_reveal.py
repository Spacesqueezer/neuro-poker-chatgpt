import cv2
import numpy as np
import pytest

from poker.hud.cards import find_cards, unread_board_faces
from poker.hud.hand import observe
from poker.hud.models import CardObservation
from poker.hud.recognition import configure_ocr
from poker.hud.session_images import saved_frame_path


def board():
    return [
        CardObservation("board", (100 + n * 90, 100, 85, 123), value, 90)
        for n, value in enumerate(("Ks", "4c", "9h"))
    ]


@pytest.mark.parametrize(
    "rect,expected",
    [
        ((380, 100, 66, 117), True),
        ((400, 100, 20, 123), True),
        ((380, 155, 66, 62), False),  # chips, not a card-height face
        ((480, 100, 66, 117), False),  # another position
        ((380, 80, 66, 117), False),  # not aligned to the board
    ],
)
def test_partial_next_face_invalidates_old_street_without_guessing(rect, expected):
    mask = np.zeros((500, 600), np.uint8)
    x, y, w, h = rect
    mask[y : y + h, x : x + w] = 255
    cards = board()
    extra = unread_board_faces(mask, [rect], cards)
    assert bool(extra) is expected
    if expected:
        hand = observe(
            cards
            + extra
            + [
                CardObservation("hero", (0, 0, 1, 1), "Jh", 90),
                CardObservation("hero", (0, 0, 1, 1), "7s", 90),
            ]
        )
        assert hand.valid is False
        assert hand.board == ("Ks", "4c", "9h", "")


def test_guard_requires_regular_board_and_does_not_duplicate_read_card():
    mask = np.full((500, 600), 255, np.uint8)
    cards = board()
    rect = (370, 100, 85, 123)
    cards.append(CardObservation("board", rect, "Ts", 90))
    assert unread_board_faces(mask, [rect], cards) == []
    cards = board()
    cards[1].roi = (205, 100, 85, 123)
    assert unread_board_faces(mask, [rect], cards) == []


def test_interior_gap_cannot_be_a_complete_previous_street():
    cards = board() + [CardObservation("board", (460, 100, 85, 123), "8c", 90)]
    extra = unread_board_faces(np.zeros((500, 600), np.uint8), [], cards)
    assert len(extra) == 1
    assert extra[0].roi == (370, 100, 85, 123)
    assert extra[0].value == "" and extra[0].confidence == 0


def test_positions_beyond_five_cards_are_not_a_board_gap():
    cards = board() + [CardObservation("board", (640, 100, 85, 123), "8c", 90)]
    assert unread_board_faces(np.zeros((500, 800), np.uint8), [], cards) == []


def test_chip_covered_interior_queen_must_not_turn_river_into_turn():
    path = saved_frame_path("artifacts/hud/sessions/session_20261005_122501_a8209d", 1172)
    if not path.is_file():
        pytest.skip("Local diagnostic source unavailable")
    configure_ocr()
    cards = find_cards(cv2.imread(str(path)))
    assert [c.value for c in cards if c.zone == "board"] == ["4d", "7h", "7d", "", "8c"]
    assert observe(cards).valid is False


@pytest.mark.parametrize("number", [1201, 1203, 1205, 1207])
def test_dimmed_showdown_card_keeps_its_position(number):
    path = saved_frame_path("artifacts/hud/sessions/session_20261004_094146_2c0c19", number)
    if not path.is_file():
        pytest.skip("Local diagnostic source unavailable")
    configure_ocr()
    cards = find_cards(cv2.imread(str(path)))
    assert [c.value for c in cards if c.zone == "board"] == ["8h", "7d", "", "6s", "6d"]
    assert observe(cards).valid is False


@pytest.mark.parametrize(
    "number,expected",
    [
        (631, ["Ks", "4c", "9h"]),
        (634, ["Ks", "4c", "9h", ""]),
        (641, ["Ks", "4c", "9h", "Ts"]),
    ],
)
def test_recorded_turn_reveal(number, expected):
    path = saved_frame_path("artifacts/hud/sessions/session_20261005_122501_a8209d", number)
    if not path.is_file():
        pytest.skip("Local diagnostic source unavailable")
    configure_ocr()
    cards = find_cards(cv2.imread(str(path)))
    assert [c.value for c in cards if c.zone == "board"] == expected
    assert observe(cards).valid is (number != 634)


def test_chip_covered_queen_must_not_leave_a_valid_flop():
    path = saved_frame_path("artifacts/hud/sessions/session_20261005_035204_be9e45", 1357)
    if not path.is_file():
        pytest.skip("Local diagnostic source unavailable")
    configure_ocr()
    cards = find_cards(cv2.imread(str(path)))
    assert [c.value for c in cards if c.zone == "board"] == ["Ac", "7s", "7c", ""]
    assert observe(cards).valid is False


def test_unknown_reveal_blocks_request_even_when_it_is_hero_turn():
    from poker.hud.decision_stream import DecisionStream
    from tests.hud.test_decision_stream import metadata, payload

    mask = np.full((500, 600), 255, np.uint8)
    cards = board()
    cards += unread_board_faces(mask, [(380, 100, 66, 117)], cards)
    cards += [CardObservation("hero", (0, 0, 1, 1), value, 90) for value in ("Jh", "7s")]
    hand = observe(cards, my_turn=True)
    request = payload()
    request.update(
        hero_hole_cards=list(hand.hero), board_cards=list(hand.board), street_name="turn"
    )
    stream = DecisionStream()
    for frame in (1, 2, 3):
        result = stream.update(request, metadata(frame), "12345678", cards_valid=hand.valid)
        if result is not None:
            assert result["would_send"] is False
            assert "cards_unknown_or_invalid" in result["blockers"]
            assert "cards_not_confident" in result["blockers"]
