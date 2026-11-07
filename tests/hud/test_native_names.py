from pathlib import Path

import cv2
import numpy as np
import pytest

from poker.hud import recognition as rec
from poker.hud.models import PlayerObservation
from poker.hud.state import TableState


def reading(name="romeo88", score=74, views=True):
    return PlayerObservation(
        (753, 211, 166, 65),
        name,
        score,
        "200",
        "recognized",
        name,
        ((name, 42), (name, score)) if views else ((name, score),),
    )


def test_four_corroborated_frames_establish_name_without_inflating_confidence():
    state = TableState()
    for _ in range(3):
        assert not state.update([reading()], (1238, 1005))[0].name
    seat = state.update([reading()], (1238, 1005))[0]
    assert seat.name == "romeo88"
    assert seat.observation.confidence == 74
    assert not seat.manual
    for _ in range(5):
        seat = state.update([reading("other")], (1238, 1005))[0]
    assert seat.name == "romeo88"


def test_single_view_or_interrupted_sequence_does_not_establish_name():
    state = TableState()
    for _ in range(6):
        assert not state.update([reading(views=False)], (1238, 1005))[0].name
    for _ in range(3):
        assert not state.update([reading()], (1238, 1005))[0].name
    state.update([], (1238, 1005))
    assert not state.update([reading()], (1238, 1005))[0].name


@pytest.mark.parametrize("number", [100, 110, 285, 988, 131])
def test_small_upper_right_name_is_not_dropped(number):
    p = (
        Path(__file__).resolve().parents[2]
        / f"artifacts/hud/sessions/session_20260914_083437_99b85d/frames/{number:08d}.jpg"
    )
    if not p.exists():
        pytest.skip("Local diagnostic frame unavailable")
    rec.configure_ocr()
    found = rec.analyze(cv2.imread(str(p)))
    player = next(r for r in found if r.roi[0] > 700 and r.roi[1] < 300)
    assert player.name == "romeo88"
    assert player.confidence >= 65


def test_colored_letters_are_not_recovered_as_a_nickname():
    rec.horizontal_background_name.cache_clear()
    crop = np.zeros((33, 160, 3), np.uint8)
    cv2.putText(crop, "CALL", (25, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
    assert rec.horizontal_background_name(crop.shape, crop.tobytes()) == ()


@pytest.mark.parametrize(
    "candidate,score,expected", [("romeo88", 74, 74), ("romeo88", 64, 42), ("romeo8s", 99, 42)]
)
def test_native_fallback_requires_agreement(monkeypatch, candidate, score, expected):
    values = iter([("romeo88", 42), ("romeo88", 22)])
    monkeypatch.setattr(rec, "ocr_line", lambda *args: next(values))
    monkeypatch.setattr(rec, "native_name_line", lambda *args: (candidate, score))
    monkeypatch.setattr(rec, "horizontal_background_name", lambda *args: ())
    text, confidence, evidence = rec.read_name_crop(np.full((33, 160, 3), 200, np.uint8))
    assert text == "romeo88"
    assert confidence == expected
    assert evidence[-1] == (candidate, score)
