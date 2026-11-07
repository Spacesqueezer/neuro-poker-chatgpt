from pathlib import Path

import cv2
import pytest

from poker.hud.cards import find_cards, is_red_card_back
from poker.hud.recognition import configure_ocr

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("number", [30, 77, 1555])
def test_dealing_back_is_not_an_unknown_board_card(number):
    path = ROOT / f"artifacts/hud/sessions/session_20260911_020140_b8974b/frames/{number:08d}.jpg"
    if not path.exists():
        pytest.skip("Local recorded session unavailable")
    configure_ocr()
    frame = cv2.imread(str(path))
    assert is_red_card_back(frame[554:651, 708:778])
    assert not [c for c in find_cards(frame) if c.zone == "board"]


def test_red_face_cards_survive_filter():
    path = ROOT / "artifacts/hud/sessions/session_20260911_020140_b8974b/frames/00001022.jpg"
    if not path.exists():
        pytest.skip("Local recorded session unavailable")
    configure_ocr()
    cards = find_cards(cv2.imread(str(path)))
    assert {"Qh", "9h", "6h"} <= {c.value for c in cards}
