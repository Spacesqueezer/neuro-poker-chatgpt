from pathlib import Path

import cv2
import numpy as np
import pytest

from poker.hud.recognition import configure_ocr
from poker.hud.session_images import saved_frame_path
from poker.hud.slider import field_and_knob, remove_field_caret


@pytest.mark.parametrize(
    "frame,value", [(539, 6), (540, 6), (1025, 208.15), (1015, 208.15), (166, 5)]
)
def test_caret_amounts_on_saved_frames(frame, value):
    root = Path("artifacts/hud/sessions/session_20261005_122501_a8209d")
    path = saved_frame_path(root, frame)
    if not path.exists():
        pytest.skip("Local capture is unavailable")
    configure_ocr()
    result = field_and_knob(cv2.imread(str(path)))
    assert result["field"]["value"] == value


def test_single_digit_caret_preserves_digit_and_trailing_one():
    mask = np.zeros((32, 100), np.uint8)
    mask[8:23, 71:79] = 255
    mask[4:28, 80] = 255
    clean, caret = remove_field_caret(mask)
    assert caret == [80, 4, 1, 24]
    assert np.array_equal(clean[:, :80], mask[:, :80])
    mask[4:28, 80] = 0
    mask[8:23, 80] = 255
    clean, caret = remove_field_caret(mask)
    assert caret is None
    assert np.array_equal(clean, mask)
