from pathlib import Path

import cv2
import pytest

from poker.hud.pipeline import analyze_frame
from poker.hud.recognition import configure_ocr
from poker.hud.session_images import saved_frame_path


@pytest.mark.parametrize("frame_id", [1404, 1407, 1410])
def test_small_nine_no_longer_blocks_confident_flop(frame_id):
    root = Path("artifacts/hud/sessions/session_20261014_041306_74a3f9")
    path = saved_frame_path(root, frame_id)
    if not path.exists():
        pytest.skip("Local diagnostic source unavailable")
    configure_ocr()
    hand = analyze_frame(cv2.imread(str(path)), include_players=False).hand
    assert hand.hero == ("Tc", "Td")
    assert hand.board == ("8s", "As", "9s")
    assert hand.valid
    assert hand.my_turn
    assert all(c.confidence >= 75 for c in hand.cards)
    assert hand.odds is not None
    assert 0 < hand.odds["improvement_probability"] < 1
