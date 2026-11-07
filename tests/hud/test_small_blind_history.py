import cv2
import numpy as np
import pytest

from poker.hud.recognition import configure_ocr, layout_panels
from poker.hud.session_images import saved_frame_path
from poker.hud.table_signals import read_blind_label


@pytest.mark.parametrize(
    "frame,expected",
    [(997, "small_blind"), (998, "small_blind"), (999, "small_blind"), (1001, None), (1098, None)],
)
def test_client_history_small_blind_and_neighboring_non_blinds(frame, expected):
    path = saved_frame_path("artifacts/hud/sessions/session_20261005_122501_a8209d", frame)
    if not path.is_file():
        pytest.skip("Local diagnostic image unavailable")
    configure_ocr()
    image = cv2.imread(str(path))
    result = read_blind_label(image, layout_panels(image)[0])
    assert (result or {}).get("blind") == expected


def test_white_mask_cannot_override_confident_conflicting_text(monkeypatch):
    # A centered muted-yellow patch passes the geometric gate.
    frame = np.zeros((80, 180, 3), np.uint8)
    frame[25:38, 82:94] = cv2.cvtColor(np.uint8([[[25, 90, 210]]]), cv2.COLOR_HSV2BGR)[0, 0]
    calls = []

    def read(*args):
        calls.append(args)
        return {"text": "другое", "words": [{"confidence": 96}]}

    monkeypatch.setattr("poker.hud.table_signals.read_roi", read)
    assert read_blind_label(frame, (0, 0, 180, 80)) is None
    assert len(calls) == 1
