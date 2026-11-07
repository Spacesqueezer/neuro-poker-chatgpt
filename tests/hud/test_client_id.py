from pathlib import Path

import cv2
import numpy as np
import pytest

from poker.hud import client_id
from poker.hud.recognition import configure_ocr


@pytest.mark.parametrize("scales", [(2, 4), (2, 3)])
@pytest.mark.parametrize("second", ["#2866761493", "#2866/61492", "2866761492"])
def test_padded_id_rejects_disagreement_and_nonliteral_number(monkeypatch, second, scales):
    values = iter(["#2866761492", second])
    monkeypatch.setattr(
        client_id.pytesseract,
        "image_to_data",
        lambda *a, **k: {"text": [next(values)], "conf": [95]},
    )
    client_id._read_padded.cache_clear()
    crop = np.zeros((100, 20, 3), np.uint8)
    assert client_id._read_padded(crop.shape, crop.tobytes(), scales) is None
    client_id._read_padded.cache_clear()


@pytest.mark.parametrize(
    "frame, expected", [(227, "2866761492"), (705, "2866764792"), (4185, "2866783765")]
)
def test_evening_session_hand_id(frame, expected):
    path = (
        Path("artifacts/hud/sessions/session_20260917_195843_ac4541/requests") / f"{frame:08d}.png"
    )
    if not path.exists():
        pytest.skip("Local session image is unavailable")
    configure_ocr()
    result = client_id.read_hand_id(cv2.imread(str(path)))
    assert result["value"] == expected
    assert result["confidence"] >= 80


@pytest.mark.parametrize(
    "frame, expected",
    [(642, "2870757396"), (976, "2870757645"), (1037, "2870757645"), (1059, "2870757645")],
)
def test_september23_window_border(frame, expected):
    path = (
        Path("artifacts/hud/sessions/session_20260923_054209_82f838/requests") / f"{frame:08d}.png"
    )
    if not path.exists():
        pytest.skip("Local session image is unavailable")
    configure_ocr()
    result = client_id.read_hand_id(cv2.imread(str(path)))
    assert result["value"] == expected
    assert result["confidence"] >= 80
    assert result["method"] == "inner_grayscale_agreement"
    assert {2, 3} <= {r["scale"] for r in result["readings"]}


@pytest.mark.parametrize("frame,expected", [(445, "2870757166"), (851, "2870757529")])
def test_inner_border_alternative_scale(frame, expected):
    path = (
        Path("artifacts/hud/sessions/session_20260923_054209_82f838/requests") / f"{frame:08d}.png"
    )
    if not path.exists():
        pytest.skip("Local session image is unavailable")
    configure_ocr()
    result = client_id.read_hand_id(cv2.imread(str(path)))
    assert result["value"] == expected
    assert result["confidence"] >= 80
    assert [r["scale"] for r in result["readings"]] == [2, 4]


@pytest.mark.parametrize("last,expected", [("#2870757166", True), ("#2870757168", False)])
def test_inner_scales_reject_any_strong_conflict(monkeypatch, last, expected):
    values = iter(["#2870757166", "#2870757166", last])
    monkeypatch.setattr(
        client_id.pytesseract,
        "image_to_data",
        lambda *a, **k: {"text": [next(values)], "conf": [90]},
    )
    client_id._read_padded.cache_clear()
    crop = np.zeros((100, 20, 3), np.uint8)
    assert (client_id._read_padded(crop.shape, crop.tobytes(), (2, 4, 3)) is not None) == expected
    client_id._read_padded.cache_clear()
