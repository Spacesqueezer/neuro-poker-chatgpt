from pathlib import Path

import cv2
import numpy as np
import pytest

from poker.hud.card_backs import card_back_pair
from poker.hud.recognition import layout_panels


@pytest.mark.parametrize(
    "height,offset,second,expected",
    [
        (28, 0, True, True),
        (27, 0, True, True),
        (26, 0, True, None),
        (28, 8, True, None),
        (28, 0, False, None),
    ],
)
def test_small_back_tolerance_still_requires_two_aligned_rectangles(
    height, offset, second, expected
):
    frame = np.zeros((300, 500, 3), np.uint8)
    frame[170 : 170 + height, 144:165] = (50, 40, 180)
    if second:
        frame[170 + offset : 170 + offset + height, 171:213] = (50, 40, 180)
    assert card_back_pair(frame, (100, 200, 166, 65))["present"] is expected


def test_small_window_recognizes_all_six_visible_opponent_pairs():
    path = Path(__file__).resolve().parents[2] / (
        "artifacts/hud/sessions/session_20260914_083437_99b85d/frames/00000551.jpg"
    )
    if not path.exists():
        pytest.skip("Local diagnostic frame unavailable")
    frame = cv2.imread(str(path))
    assert {
        i for i, roi in enumerate(layout_panels(frame)) if card_back_pair(frame, roi)["present"]
    } == set(range(6))


@pytest.mark.parametrize("number,expected", [(1, {0, 2, 4}), (86, {0, 5}), (1675, set())])
def test_visible_pairs_do_not_confuse_avatar_or_face_up_cards(number, expected):
    path = Path(__file__).resolve().parents[2] / (
        f"artifacts/hud/sessions/session_20260911_012959_8898f1/frames/{number:08}.jpg"
    )
    if not path.exists():
        pytest.skip("Local diagnostic frame unavailable")
    image = cv2.imread(str(path))
    readings = [card_back_pair(image, roi) for roi in layout_panels(image)]
    assert {i for i, r in enumerate(readings) if r["present"] is True} == expected
    assert all(r["present"] is None for i, r in enumerate(readings) if i not in expected)


def test_september23_raster_height_and_folded_seat():
    path = Path("artifacts/hud/sessions/session_20260923_054209_82f838/requests/00000503.png")
    if not path.exists():
        pytest.skip("Local diagnostic frame unavailable")
    frame = cv2.imread(str(path))
    assert {
        i for i, roi in enumerate(layout_panels(frame)) if card_back_pair(frame, roi)["present"]
    } == {1, 3, 4}
