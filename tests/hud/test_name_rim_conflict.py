from pathlib import Path

import cv2
import numpy as np
import pytest

from poker.hud import recognition
from poker.hud.models import PlayerObservation
from poker.hud.state import TableState


@pytest.mark.parametrize(
    "checks,rejected",
    [
        ((("romanstep", 91), ("romanstep", 87)), True),
        ((("omanstep", 91), ("omanstep", 87)), False),
        ((("romanstep", 91), ("romanstep", 84)), False),
        ((("romanstep", 91), ("romansten", 87)), False),
        ((), False),
    ],
)
def test_confident_name_conflict_needs_two_strong_complete_readings(monkeypatch, checks, rejected):
    monkeypatch.setattr(recognition, "ocr_line", lambda image: ("omanstep", 89))
    monkeypatch.setattr(recognition, "rim_name_crosscheck", lambda *args: checks)
    text, confidence, alternatives = recognition.read_name_crop(
        np.full((34, 166, 3), 180, np.uint8)
    )
    assert text == "omanstep"  # Raw evidence survives; no inferred alias.
    assert confidence == (0 if rejected else 89)
    assert alternatives[0] == ("omanstep", 89)


def test_conflicting_dim_name_does_not_replace_confirmed_player():
    path = Path("artifacts/hud/sessions/session_20261015_110216_51a6bd/ocr_frames/00000216.png")
    if not path.exists():
        pytest.skip("Local diagnostic source unavailable")
    recognition.configure_ocr()
    frame = cv2.imread(str(path))
    roi = (327, 218, 172, 67)
    player = recognition.analyze_panel(frame, roi, [])
    assert player.name == ""
    assert player.raw_name == "omanstep"
    assert player.confidence == 0
    assert ("romanstep", 91) in player.ocr_candidates
    state = TableState()
    prior = PlayerObservation(roi, "romanstep", 95, "206.90", "recognized")
    for _ in range(3):
        state.update([prior], (1280, 1040))
    for _ in range(4):
        state.update([player], (1280, 1040))
    assert len(state.seats) == 1
    assert next(iter(state.seats.values())).name == "romanstep"


def test_plain_background_does_not_trigger_extra_ocr(monkeypatch):
    def unexpected(*args):
        raise AssertionError("No OCR needed without a crossing rim")

    monkeypatch.setattr(recognition, "ocr_line", unexpected)
    recognition.rim_name_crosscheck.cache_clear()
    crop = np.full((34, 166, 3), 50, np.uint8)
    assert recognition.rim_name_crosscheck(crop.shape, crop.tobytes()) == ()
