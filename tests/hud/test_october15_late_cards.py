from pathlib import Path

import cv2
import pytest

from poker.hud.pipeline import analyze_frame
from poker.hud.recognition import configure_ocr


@pytest.mark.parametrize("frame_id", [1195, 1203, 1205])
def test_corner_six_resolves_chip_obscured_large_rank(frame_id):
    path = (
        Path("artifacts/hud/sessions/session_20261015_110216_51a6bd/ocr_frames")
        / f"{frame_id:08d}.png"
    )
    if not path.exists():
        pytest.skip("Local diagnostic source unavailable")
    configure_ocr()
    hand = analyze_frame(cv2.imread(str(path)), include_players=False).hand
    assert hand.hero == ("Kd", "Jd")
    assert hand.board == ("Th", "Qs", "3c", "6s", "Kc")
    assert hand.valid
    assert hand.odds is not None
    assert hand.my_turn is (frame_id == 1195)
