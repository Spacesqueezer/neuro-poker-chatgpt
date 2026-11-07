import numpy as np
import pytest

from poker.hud import slider, table_signals


@pytest.fixture(autouse=True)
def isolate_cache():
    table_signals.numeric_words.cache_clear()
    yield
    table_signals.numeric_words.cache_clear()


def test_field_cache_requires_identical_pixels_and_returns_fresh_result(monkeypatch):
    seen = []

    def ocr(view, **kwargs):
        seen.append(view.copy())
        return {"text": ["", "12.50"], "conf": [-1, 96]}

    monkeypatch.setattr(table_signals.pytesseract, "image_to_data", ocr)
    pixels = np.zeros((10, 20), np.uint8)
    first = slider.read_field_view(pixels)
    first["value"] = 999
    assert slider.read_field_view(pixels.copy())["value"] == 12.5
    assert len(seen) == 1
    pixels[2, 2] = 255
    assert slider.read_field_view(pixels)["value"] == 12.5
    assert len(seen) == 2


def test_numeric_cache_includes_shape_and_ocr_mode_and_is_bounded(monkeypatch):
    calls = []

    def ocr(view, **kwargs):
        calls.append((view.shape, kwargs["config"]))
        return {"text": ["5"], "conf": [98]}

    monkeypatch.setattr(table_signals.pytesseract, "image_to_data", ocr)
    read = table_signals.numeric_words
    assert read((2, 2), b"abcd", "--psm 7") == (("5", 98.0),)
    read((2, 2), b"abcd", "--psm 7")
    read((1, 4), b"abcd", "--psm 7")
    read((2, 2), b"abcd", "--psm 13")
    assert len(calls) == 3
    for i in range(130):
        read((1, 2), i.to_bytes(2, "little"), "--psm 7")
    assert read.cache_info().currsize == 128


def test_button_cache_keeps_current_coordinates_and_checks_current_expected_value(monkeypatch):
    calls = []

    def ocr(view, **kwargs):
        calls.append(kwargs["config"])
        # The first pass is weak; only agreement with the current word may recover it.
        return (
            {"text": ["1"], "conf": [35]}
            if "13" in kwargs["config"]
            else {"text": ["16"], "conf": [96]}
        )

    monkeypatch.setattr(table_signals.pytesseract, "image_to_data", ocr)
    frame = np.zeros((100, 200, 3), np.uint8)
    word = {"text": "16", "confidence": 95, "roi": [10, 10, 18, 19]}
    first = table_signals.button_number(frame, (0, 0, 50, 50), word)
    moved = table_signals.button_number(frame, (100, 20, 50, 50), word)
    assert moved["value"] == first["value"] == 16
    assert moved["roi"] == [110, 30, 18, 19]
    assert moved["grayscale_check"]["roi"] == [106, 26, 26, 27]
    changed = table_signals.button_number(frame, (100, 20, 50, 50), {**word, "text": "17"})
    assert changed["confidence"] < 85
    assert changed.get("method") is None
    assert len(calls) == 2
