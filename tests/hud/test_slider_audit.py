from pathlib import Path

import cv2
import numpy as np
import pytest

from poker.hud.recognition import configure_ocr
from poker.hud.slider import EndpointConfirmation, field_and_knob, remove_field_caret


@pytest.mark.parametrize(
    "number,value,endpoint",
    [
        (1908, 341.88, "right"),
        (1910, 341.88, "right"),
        (1912, 65.0, "interior"),
        (1914, 4.0, "left"),
    ],
)
def test_independent_field_reading_and_rail(number, value, endpoint):
    path = (
        Path(__file__).resolve().parents[2]
        / f"artifacts/hud/sessions/session_20260912_074919_b1e521/frames/{number:08d}.jpg"
    )
    if not path.exists():
        pytest.skip("Local diagnostic frame unavailable")
    configure_ocr()
    result = field_and_knob(cv2.imread(str(path)))
    assert result["field"]["value"] == value
    assert result["knob"] is not None
    assert result["endpoint"] == endpoint
    assert result["rail"]["legal_bound_confirmed"] is False


def test_blank_image_does_not_produce_slider_evidence():
    assert field_and_knob(np.zeros((1283, 1580, 3), dtype=np.uint8)) == {
        "field": None,
        "knob": None,
        "endpoint": None,
    }


@pytest.mark.parametrize("number", [1580, 2967])
def test_clipped_field_cannot_supply_a_decimal_or_endpoint(number):
    path = (
        Path(__file__).resolve().parents[2]
        / f"artifacts/hud/sessions/session_20260912_114052_d37ed0/frames/{number:08d}.jpg"
    )
    if not path.exists():
        pytest.skip("Local diagnostic frame unavailable")
    result = field_and_knob(cv2.imread(str(path)))
    assert result["field"] is None
    assert result["endpoint"] is None


def test_same_left_knob_position_can_show_different_amounts():
    root = (
        Path(__file__).resolve().parents[2]
        / "artifacts/hud/sessions/session_20260912_074919_b1e521/frames"
    )
    if not all((root / f"{n:08d}.jpg").exists() for n in (1954, 1958)):
        pytest.skip("Local diagnostic frames unavailable")
    configure_ocr()
    first, second = [field_and_knob(cv2.imread(str(root / f"{n:08d}.jpg"))) for n in (1954, 1958)]
    assert first["knob"]["roi"] == second["knob"]["roi"]
    assert (first["field"]["value"], second["field"]["value"]) == (8, 10)
    assert all(r["rail"]["legal_bound_confirmed"] is False for r in (first, second))


def test_caret_removal_keeps_a_thin_digit_one():
    mask = np.zeros((42, 80), np.uint8)
    mask[13:27, 10:17] = 255
    mask[13:27, 25:32] = 255
    mask[13:27, 40:41] = 255
    clean, caret = remove_field_caret(mask)
    assert caret is None
    assert np.array_equal(clean, mask)
    mask[9:33, 50:51] = 255
    clean, caret = remove_field_caret(mask)
    assert caret == [50, 9, 1, 24]
    assert np.array_equal(clean[:, :50], mask[:, :50])
    assert not clean[:, 50:].any()


def observation(frame=1):
    return {
        "frame_id": frame,
        "captured_at": f"2026-09-12T05:00:{frame:02d}+00:00",
        "image": f"{frame}.jpg",
        "window": "table",
        "client_rect": [0, 0, 1580, 1283],
        "controls": {
            "flags": {"can_call": True},
            "call_amount": 2,
            "selected_wager": {"action": "raise", "value": 4},
        },
    }


@pytest.mark.parametrize(
    "change",
    [
        "hand",
        "window",
        "rect",
        "gap",
        "duplicate",
        "amount",
        "call",
        "interior",
        "missing_geometry",
        "street",
        "epoch",
    ],
)
def test_endpoint_confirmation_resets_on_uncertainty_and_boundaries(change):
    tracker = EndpointConfirmation()
    identity = {"value": "2862525208", "confidence": 95}
    evidence = {"endpoint": "left", "field": {"value": 4}}
    assert tracker.update(observation(), identity, evidence) is None
    row = observation(2)
    if change == "hand":
        identity = {**identity, "value": "2862525253"}
    if change == "window":
        row["window"] = "other"
    if change == "rect":
        row["client_rect"][0] = 1
    if change == "gap":
        row = observation(10)
    if change == "duplicate":
        row = observation(1)
    if change == "amount":
        evidence = {**evidence, "field": {"value": 8}}
    if change == "call":
        row["controls"]["call_amount"] = 5
    if change == "interior":
        evidence = {**evidence, "endpoint": "interior"}
    if change == "missing_geometry":
        row.pop("client_rect")
    if change == "street":
        row["board_cards"] = ["Ah", "Kd", "2c"]
    if change == "epoch":
        row["evidence_epoch"] = 2
    assert tracker.update(row, identity, evidence) is None


def test_endpoint_requires_two_current_frames_and_keeps_sources():
    tracker = EndpointConfirmation()
    identity = {"value": "2862525208", "confidence": 95}
    evidence = {"endpoint": "left", "field": {"value": 4}}
    assert tracker.update(observation(), identity, evidence) is None
    result = tracker.update(observation(2), identity, evidence)
    assert result["value"] == 4
    assert [s["frame_id"] for s in result["confirmation_frames"]] == [1, 2]
    assert result["legal_bound_confirmed"] is False
    assert tracker.update(observation(3), identity, {"endpoint": None}) is None


@pytest.mark.parametrize(
    "number", [83, 213, 743, 851, 858, 885, 976, 980, 1037, 1059, 1153, 1158, 1189, 1257]
)
def test_small_currency_field_keeps_complete_text(number):
    path = (
        Path("artifacts/hud/sessions/session_20260923_054209_82f838/requests") / f"{number:08d}.png"
    )
    if not path.exists():
        pytest.skip("Local diagnostic frame unavailable")
    configure_ocr()
    result = field_and_knob(cv2.imread(str(path)))
    assert result["field"]["value"] == 2
    assert result["field"]["method"] == "tight_currency_polarities_agree"
    assert result["rail"]["legal_bound_confirmed"] is False


def test_tight_field_does_not_override_conflicting_mask(monkeypatch):
    from poker.hud import slider

    readings = iter([{"value": None}, {"value": 20}, {"value": None}])
    monkeypatch.setattr(slider, "read_field_view", lambda view: next(readings))
    monkeypatch.setattr(
        slider, "polarity_currency_amount", lambda *args: {"value": 2, "readings": []}
    )
    result = slider.read_field(np.full((30, 100, 3), 255, np.uint8))
    assert result["value"] is None
    assert result["tight_evidence"]["conflicting_values"] == [20]
