from pathlib import Path

import cv2
import numpy as np
import pytest

from poker.hud import seat_evidence
from poker.hud.recognition import configure_ocr, layout_panels


@pytest.mark.parametrize("number", [146, 156, 163, 362, 368, 372, 376])
def test_dim_leading_digits_cannot_be_lost_by_color_crop(number):
    path = (
        Path("artifacts/hud/sessions/session_20261004_094146_2c0c19/requests") / f"{number:08d}.png"
    )
    if not path.exists():
        pytest.skip("Local diagnostic frame unavailable")
    configure_ocr()
    image = cv2.imread(str(path))
    reading = seat_evidence.read_stack(image, layout_panels(image)[3], read_status=False)
    assert reading["value"] is None
    assert reading["text"] == "344,48 p."


def test_tight_currency_needs_matching_full_width_number(monkeypatch):
    crop = np.full((30, 160, 3), (20, 130, 130), np.uint8)
    readings = iter(
        [
            {"value": None, "readings": []},
            {"value": 4.48, "readings": [{"value": 4.48, "confidence": 95}] * 2},
        ]
    )
    monkeypatch.setattr(seat_evidence, "polarity_currency_amount", lambda *a: next(readings))
    result = seat_evidence.yellow_stack_amount(
        crop, number_words=[{"text": "344,48", "confidence": 95}, {"text": "p.", "confidence": 90}]
    )
    assert result["value"] is None


@pytest.mark.parametrize("frame,seat,expected", [(175, 1, 107.62), (987, 0, 208.18), (1033, 4, 0)])
def test_stack_red_channel_preserves_digits_over_felt(frame, seat, expected):
    path = (
        Path("artifacts/hud/sessions/session_20260924_102223_ea7318/ocr_frames") / f"{frame:08}.png"
    )
    if not path.exists():
        pytest.skip("Local diagnostic frame unavailable")
    configure_ocr()
    image = cv2.imread(str(path))
    reading = seat_evidence.read_stack(image, layout_panels(image)[seat], read_status=False)
    assert reading["value"] == expected
    assert reading["method"] == "red_channel_polarity_agreement"
    assert reading["confidence"] >= 85


@pytest.mark.parametrize(
    "first,second,score,expected",
    [
        ("0 p.", "0 p.", 85, 0),
        ("O p.", "O p.", 99, None),
        ("200 p.", "206 p.", 95, None),
        ("200 p.", "200 p.", 84, None),
        ("-90 p.", "90 p.", 99, None),
        ("200", "200", 99, None),
    ],
)
def test_red_channel_requires_complete_unsigned_currency(
    monkeypatch, first, second, score, expected
):
    values = iter([first, second])
    monkeypatch.setattr(
        seat_evidence.pytesseract,
        "image_to_data",
        lambda *a, **k: {"text": [next(values)], "conf": [score]},
    )
    crop = np.full((40, 200, 3), (20, 130, 130), np.uint8)
    assert seat_evidence.red_stack_amount(crop)["value"] == expected


def test_red_stack_skips_ocr_without_currency_colored_pixels(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Empty stack should not trigger more OCR")

    monkeypatch.setattr(seat_evidence.pytesseract, "image_to_data", forbidden)
    assert seat_evidence.red_stack_amount(np.zeros((40, 200, 3), np.uint8))["value"] is None


@pytest.mark.parametrize(
    "frame,seat,expected",
    [(83, 4, 200), (642, 1, 67.14), (1037, 3, 86), (1059, 3, 86)],
)
def test_transparent_and_low_confidence_stack(frame, seat, expected):
    path = (
        Path("artifacts/hud/sessions/session_20260923_054209_82f838/requests") / f"{frame:08}.png"
    )
    if not path.exists():
        pytest.skip("Local diagnostic frame unavailable")
    configure_ocr()
    image = cv2.imread(str(path))
    reading = seat_evidence.read_stack(image, layout_panels(image)[seat], read_status=False)
    assert reading["value"] == expected
    assert reading["confidence"] >= 85
    assert reading["original"]["value"] is None


def test_narrow_only_stack_stays_unknown_without_full_width_corroboration():
    path = Path("artifacts/hud/sessions/session_20260923_054209_82f838/requests/00000450.png")
    if not path.exists():
        pytest.skip("Local diagnostic frame unavailable")
    configure_ocr()
    image = cv2.imread(str(path))
    reading = seat_evidence.read_stack(image, layout_panels(image)[5], read_status=False)
    # Previously accepted 251.68 from a crop alone. The full numeric token has
    # confidence 81; keep unknown rather than reintroduce leading-digit loss.
    assert reading["value"] is None


@pytest.mark.parametrize(
    "second,score,expected",
    [
        ("200 p.", 85, 200),
        ("206 p.", 95, None),
        ("200 p.", 84, None),
        ("200", 95, None),
        ("Op.", 99, None),
    ],
)
def test_tight_stack_requires_exact_currency_agreement(monkeypatch, second, score, expected):
    seat_evidence.polarity_currency_amount.cache_clear()
    values = iter([("200 p.", 95), (second, score)])

    def ocr(*args, **kwargs):
        text, confidence = next(values)
        return {"text": [text], "conf": [confidence]}

    monkeypatch.setattr(seat_evidence.pytesseract, "image_to_data", ocr)
    assert (
        seat_evidence.yellow_stack_amount(np.full((30, 100, 3), (20, 130, 130), np.uint8))["value"]
        == expected
    )


def test_yellow_stack_cannot_override_strong_gray_disagreement(monkeypatch):
    seat_evidence.stack_pixels.cache_clear()
    monkeypatch.setattr(
        seat_evidence.pytesseract, "image_to_data", lambda *a, **k: {"text": ["bad"], "conf": [0]}
    )
    monkeypatch.setattr(
        seat_evidence,
        "polarity_currency_amount",
        lambda *a: {
            "value": None,
            "readings": [{"value": 200, "text": "200 p."}, {"value": None, "text": ""}],
        },
    )
    monkeypatch.setattr(
        seat_evidence, "yellow_stack_amount", lambda *a, **k: {"value": 206, "readings": []}
    )
    crop = np.zeros((30, 100, 3), np.uint8)
    result = seat_evidence.stack_pixels(crop.shape, crop.tobytes())
    assert result["value"] is None
    assert result["retry_evidence"]["conflicting_values"] == [200]
    seat_evidence.stack_pixels.cache_clear()


@pytest.mark.parametrize("stage", [0, 1])
@pytest.mark.parametrize("sign", ["+", "-", "−"])
def test_signed_amount_cannot_be_cropped_into_stack(monkeypatch, stage, sign):
    seat_evidence.stack_pixels.cache_clear()
    seat_evidence.polarity_currency_amount.cache_clear()
    texts = iter([f"{sign}90 p." if stage == 0 else "bad", f"{sign}90 p.", "90 p."])
    monkeypatch.setattr(
        seat_evidence.pytesseract,
        "image_to_data",
        lambda *a, **k: {"text": [next(texts)], "conf": [92]},
    )
    crop = np.zeros((30, 100, 3), np.uint8)
    reading = seat_evidence.stack_pixels(crop.shape, crop.tobytes())
    assert reading["value"] is None
    assert reading["rejection"] == "signed_amount_not_stack"
    seat_evidence.stack_pixels.cache_clear()
    seat_evidence.polarity_currency_amount.cache_clear()


def test_real_signed_stack_overlay_rejected():
    path = Path("artifacts/hud/sessions/session_20260923_054209_82f838/frames/00000724.jpg")
    if not path.exists():
        pytest.skip("Local diagnostic frame unavailable")
    configure_ocr()
    reading = seat_evidence.read_stack(
        cv2.imread(str(path)), [1033, 380, 166, 65], read_status=False
    )
    assert reading["value"] is None
    assert reading["rejection"] == "signed_amount_not_stack"
