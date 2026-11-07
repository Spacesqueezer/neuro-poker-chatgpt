from pathlib import Path

import cv2
import pytest

from poker.hud.pipeline import analyze_frame
from poker.hud.recognition import configure_ocr
from poker.hud.session_images import saved_frame_path


@pytest.mark.parametrize(
    "frame_id,hero,board",
    [
        (753, ("Qd", "Jd"), ("7d", "6c", "Th")),
        (776, ("Qd", "Jd"), ("7d", "6c", "Th", "4h")),
        (799, ("Qd", "Jd"), ("7d", "6c", "Th", "4h", "8h")),
        (1562, ("Js", "3s"), ("6s", "3d", "Td")),
        (1564, ("Js", "3s"), ("6s", "3d", "Td")),
        (1566, ("Js", "3s"), ("6s", "3d", "Td")),
    ],
)
def test_medium_ten_allows_odds_without_lowering_card_threshold(frame_id, hero, board):
    root = Path("artifacts/hud/sessions/session_20261015_090831_f9d6b3")
    path = saved_frame_path(root, frame_id)
    if not path.exists():
        pytest.skip("Local diagnostic source unavailable")
    configure_ocr()
    hand = analyze_frame(cv2.imread(str(path)), include_players=False).hand
    assert hand.hero == hero
    assert hand.board == board
    assert hand.valid and hand.my_turn
    assert all(card.confidence >= 75 for card in hand.cards)
    assert hand.odds is not None
    assert 0 <= hand.odds["improvement_probability"] <= 1
