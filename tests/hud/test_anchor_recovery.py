from pathlib import Path

import cv2
import numpy as np
import pytest

from poker.hud import client_id, context, table_signals
from poker.hud.recognition import configure_ocr, layout_panels

SESSION = Path("artifacts/hud/sessions/session_20260930_232949_0c3f84/ocr_frames")


@pytest.mark.parametrize("number", [724, 1224, 1229, 1233, 1240, 1244, 1449, 1506, 1512])
def test_small_dealer_next_to_hero(number):
    path = (
        Path("artifacts/hud/sessions/session_20261004_094146_2c0c19/requests") / f"{number:08}.png"
    )
    if not path.exists():
        pytest.skip("Local diagnostic image unavailable")
    configure_ocr()
    image = cv2.imread(str(path))
    found = context.dealer_candidates(image)
    assert len(found) == 1
    assert table_signals.locate_dealer(layout_panels(image), found) == 6
    assert found[0]["circle_threshold"] == 18


@pytest.mark.parametrize("number", [630, 637])
def test_native_currency_reading_recovers_one_ruble_call(number):
    path = (
        Path("artifacts/hud/sessions/session_20261004_094146_2c0c19/requests") / f"{number:08}.png"
    )
    if not path.exists():
        pytest.skip("Local diagnostic image unavailable")
    configure_ocr()
    assert table_signals.controls(cv2.imread(str(path)))["call_amount"] == 1


def test_native_currency_cannot_override_confident_previous_polarity(monkeypatch):
    path = Path("artifacts/hud/sessions/session_20261004_094146_2c0c19/requests/00000630.png")
    if not path.exists():
        pytest.skip("Local diagnostic image unavailable")
    configure_ocr()
    original = table_signals.polarity_currency_amount

    def conflicting(*args, scale=2):
        if scale == 1:
            return {"value": 7, "readings": [{"value": 7, "confidence": 99}] * 2}
        return original(*args)

    monkeypatch.setattr(table_signals, "polarity_currency_amount", conflicting)
    assert table_signals.controls(cv2.imread(str(path)))["call_amount"] is None


def frame(number):
    path = SESSION / f"{number:08}.png"
    if not path.exists():
        pytest.skip("Local diagnostic image unavailable")
    configure_ocr()
    return cv2.imread(str(path))


@pytest.mark.parametrize("number", [362, 480, 877])
def test_dealer_circle_touching_hero_cards(number):
    image = frame(number)
    candidates = context.dealer_candidates(image)
    assert table_signals.locate_dealer(layout_panels(image), candidates) == 6
    assert len(candidates) == 1
    assert candidates[0]["method"] == "anchor_circle_inner_glyph"


def test_circle_without_confirmed_d_is_rejected(monkeypatch):
    image = frame(362)
    monkeypatch.setattr(context, "dealer_glyph", lambda *a: False)
    assert context.anchored_dealer_candidates(image) == []


@pytest.mark.parametrize("number,expected", [(171, 9), (877, 7.4), (949, 3), (1204, 7.56)])
def test_green_pot_caption_without_global_ocr_anchor(number, expected):
    result = table_signals.pot(frame(number), {})
    assert result["value"] == expected
    assert len(result["readings"]) == 2
    assert all(r["value"] == expected for r in result["readings"])


@pytest.mark.parametrize(
    "first,second,score",
    [
        ("Банк: 9 р.", "Банк: 8 р.", 95),
        ("9 р.", "9 р.", 95),
        ("Банк: -9 р.", "Банк: -9 р.", 95),
        ("Банк: 9 р.", "Банк: 9 р.", 84),
    ],
)
def test_pot_requires_anchor_unsigned_full_line_and_agreement(monkeypatch, first, second, score):
    texts = iter((first, second))
    monkeypatch.setattr(
        table_signals,
        "read_text",
        lambda *a: {"text": next(texts), "words": [{"confidence": score}]},
    )
    image = np.full((1000, 1400, 3), (0, 255, 0), np.uint8)
    assert table_signals.anchored_pot(image)["value"] is None


@pytest.mark.parametrize("number,expected", [(877, "2876688767"), (1204, "2876689857")])
def test_native_scale_hand_number_agrees_with_enlarged_read(number, expected):
    result = client_id.read_hand_id(frame(number))
    assert result["value"] == expected
    assert result["confidence"] >= 80
    assert {1, 2} <= {r["scale"] for r in result["readings"]}
