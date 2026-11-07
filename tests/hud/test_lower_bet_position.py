from pathlib import Path

import cv2
import numpy as np
import pytest

from poker.hud import table_signals as signals
from poker.hud.recognition import configure_ocr, layout_panels


@pytest.mark.parametrize("number,seat,value", [(1580, 5, 28.35), (1872, 4, 3.78), (2684, 5, 5.67)])
def test_visible_bet_above_old_roi(number, seat, value):
    root = Path(__file__).resolve().parents[2]
    path = root / f"artifacts/hud/sessions/session_20260912_114052_d37ed0/frames/{number:08d}.jpg"
    if not path.exists():
        pytest.skip("Local recorded session unavailable")
    configure_ocr()
    frame = cv2.imread(str(path))
    result = signals.read_bets(frame, layout_panels(frame))
    assert result[seat]["value"] == value
    assert result[seat]["position_evidence"]["confidence"] >= 85
    assert result[9 - seat]["value"] is None


@pytest.mark.parametrize(
    "seat,reading", [(0, {"value": None}), (5, {"value": 12}), (4, {"value": None, "text": "3p."})]
)
def test_existing_or_conflicting_evidence_is_not_replaced(monkeypatch, seat, reading):
    def unexpected(*args):
        pytest.fail("Must not OCR another position")

    monkeypatch.setattr(signals, "grayscale_amount", unexpected)
    assert (
        signals.lower_bet_position(np.zeros((50, 50, 3), np.uint8), (0, 0, 10, 10), seat, reading)
        is reading
    )


def test_empty_alternate_region_skips_ocr(monkeypatch):
    def unexpected(*args):
        pytest.fail("Empty felt must not invoke OCR")

    monkeypatch.setattr(signals, "grayscale_amount", unexpected)
    original = {"value": None, "text": ""}
    assert (
        signals.lower_bet_position(
            np.zeros((200, 200, 3), np.uint8), (50, 120, 40, 20), 4, original
        )
        is original
    )


@pytest.mark.parametrize("obstruction", ["crossing_stroke", "signed_full_read"])
def test_inner_amount_cannot_trim_stroke_or_sign(monkeypatch, obstruction):
    frame = np.zeros((300, 400, 3), np.uint8)
    roi = (100, 200, 100, 40)
    # Alternate box: x=215, y=124, w=60, h=16; cut row=5.
    frame[133:138, 230:238] = 255
    if obstruction == "crossing_stroke":
        frame[128:131, 230:238] = 255
    monkeypatch.setattr(
        signals, "grayscale_amount", lambda *a: {"value": None, "text": "", "confidence": 0}
    )
    monkeypatch.setattr(signals, "recover_bet_polarities", lambda f, r: r)
    calls = []

    def read(*args):
        calls.append(1)
        assert len(calls) == 1, "Must not crop through stroke or remove a sign"
        text = "-2 p." if obstruction == "signed_full_read" else ""
        return {"value": None, "readings": [{"value": None, "text": text}] * 2}

    monkeypatch.setattr(signals, "polarity_currency_amount", read)
    result = signals.lower_bet_position(frame, roi, 4, {"value": None, "text": ""})
    assert result["value"] is None
    assert len(calls) == 1
