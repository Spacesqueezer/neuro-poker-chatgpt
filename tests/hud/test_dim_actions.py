from pathlib import Path

import cv2
import pytest

from poker.hud.recognition import configure_ocr
from poker.hud.table_signals import read_action_label, read_settlement_label


@pytest.mark.parametrize(
    "frame,roi,action",
    [
        (1273, [98, 717, 166, 65], "fold"),
        (1597, [531, 824, 166, 65], "bet"),
        (1625, [749, 210, 166, 65], "bet"),
        (1485, [1033, 381, 166, 65], "all_in"),
        (944, [749, 210, 166, 65], None),
        (1724, [924, 717, 156, 61], None),
    ],
)
def test_saved_action_captions(frame, roi, action):
    path = Path(f"artifacts/hud/sessions/session_20260923_054209_82f838/frames/{frame:08}.jpg")
    if not path.exists():
        pytest.skip("Local diagnostic image unavailable")
    configure_ocr()
    result = read_action_label(cv2.imread(str(path)), roi)
    assert (result or {}).get("action") == action
    if action == "all_in":
        assert result["semantics"] == "visible_all_in_label_not_call_or_raise"


def test_fading_payout_is_not_bet_action():
    path = Path("artifacts/hud/sessions/session_20260923_054209_82f838/frames/00001079.jpg")
    if not path.exists():
        pytest.skip("Local diagnostic image unavailable")
    configure_ocr()
    image = cv2.imread(str(path))
    roi = [531, 823, 166, 65]
    assert read_action_label(image, roi) is None
    assert read_settlement_label(image, roi)["phase"] == "pot_awarded"
