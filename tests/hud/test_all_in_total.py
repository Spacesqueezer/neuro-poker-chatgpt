from pathlib import Path

import cv2
import pytest

from poker.hud.recognition import configure_ocr, layout_panels
from poker.hud.seat_evidence import read_stack
from poker.hud.table_signals import TESSDATA, controls, read_bets


@pytest.mark.parametrize("frame_id,expected", [(986, 245.94), (1713, 226.18)])
def test_all_in_button_includes_the_already_posted_big_blind(frame_id, expected):
    path = (
        Path(__file__).resolve().parents[2]
        / f"artifacts/hud/sessions/session_20260914_083437_99b85d/frames/{frame_id:08d}.jpg"
    )
    if not path.exists() or not (TESSDATA / "rus.traineddata").exists():
        pytest.skip("Local diagnostic frames / Russian OCR unavailable")
    configure_ocr()
    frame = cv2.imread(str(path))
    rois = layout_panels(frame)
    stack = read_stack(frame, rois[6])["value"]
    contribution = read_bets(frame, rois)[6]["value"]
    selected = controls(frame)["selected_wager"]
    assert contribution == 2
    assert selected["action"] == "all_in"
    assert selected["value"] == expected == round(stack + contribution, 2)
    assert selected["value"] != stack
