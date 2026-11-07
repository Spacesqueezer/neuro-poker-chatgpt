from pathlib import Path

import cv2
import numpy as np
import pytest

from poker.hud import recognition
from poker.hud.session_images import saved_frame_path


def test_maska_under_diagonal_rim():
    path = saved_frame_path(Path("artifacts/hud/sessions/session_20261005_122501_a8209d"), 228)
    if not path.exists():
        pytest.skip("Local capture is unavailable")
    recognition.configure_ocr()
    image = cv2.imread(str(path))
    text, confidence, alternatives = recognition.read_name_crop(image[740:774, 996:1160])
    assert text == "maska19"
    assert 85 <= confidence < 90
    assert alternatives[-2:] == (("maska19", 86.0), ("maska19", 88.0))


def test_no_diagonal_no_extra_ocr(monkeypatch):
    def unexpected(*args):
        raise AssertionError("No line to recover")

    monkeypatch.setattr(recognition, "ocr_line", unexpected)
    crop = np.zeros((35, 165, 3), np.uint8)
    assert recognition.diagonal_background_name(crop.shape, crop.tobytes()) == ()


@pytest.mark.parametrize(
    "checks",
    [
        (("other", 95), ("other", 95)),
        (("maska19", 95), ("maskal9", 95)),
        (("maska19", 84), ("maska19", 95)),
    ],
)
def test_diagonal_fallback_needs_original_token_and_two_confident_agreements(monkeypatch, checks):
    monkeypatch.setattr(recognition, "ocr_line", lambda image: ("— maska19", 60))
    monkeypatch.setattr(recognition, "native_name_line", lambda *args: ("— maska19", 60))
    monkeypatch.setattr(recognition, "horizontal_background_name", lambda *args: ())
    monkeypatch.setattr(recognition, "diagonal_background_name", lambda *args: checks)
    text, _, _ = recognition.read_name_crop(np.full((34, 164, 3), 160, np.uint8))
    assert text == "— maska19"
