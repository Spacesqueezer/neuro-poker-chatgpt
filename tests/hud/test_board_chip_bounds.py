from pathlib import Path

import cv2
import numpy as np
import pytest

from poker.hud.cards import board_face_bounds, find_cards
from poker.hud.recognition import configure_ocr


@pytest.mark.parametrize(
    "frame,expected", [(1150, "4s"), (1191, "4s"), (1589, "Tc"), (1591, "Tc"), (1593, "Tc")]
)
def test_chips_do_not_hide_printed_board_rank(frame, expected):
    path = Path(f"artifacts/hud/sessions/session_20260923_054209_82f838/frames/{frame:08}.jpg")
    if not path.exists():
        pytest.skip("Local diagnostic frame unavailable")
    configure_ocr()
    cards = [c for c in find_cards(cv2.imread(str(path))) if c.zone == "board"]
    assert cards[2].value == expected
    assert cards[2].confidence >= 75
    assert cards[2].roi[3] == 122


def test_board_bounds_need_two_matching_peers_and_filled_top():
    mask = np.zeros((1000, 1231), np.uint8)
    mask[416:538, 571:657] = 255
    mask[418:420, 571:657] = 0
    mask[418:420, 573:655] = 255
    rect = (571, 416, 94, 144)
    peers = [(392, 416, 84, 122), (481, 416, 85, 122)]
    assert board_face_bounds(mask, rect, peers) == (571, 416, 86, 122)
    assert board_face_bounds(mask, rect, peers[:1]) is None
    assert board_face_bounds(mask, rect, [peers[0], (481, 416, 95, 137)]) is None
    assert board_face_bounds(np.zeros_like(mask), rect, peers) is None
