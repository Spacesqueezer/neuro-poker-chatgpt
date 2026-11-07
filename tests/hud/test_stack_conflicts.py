import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from poker.hud import seat_evidence
from poker.hud.recognition import configure_ocr
from poker.hud.session_images import saved_frame_path


@pytest.mark.parametrize("other,expected", [(59.26, None), (99.26, 99.26), (None, 99.26)])
def test_high_confidence_original_does_not_override_other_confident_scale(
    monkeypatch, other, expected
):
    seat_evidence.stack_pixels.cache_clear()
    monkeypatch.setattr(
        seat_evidence.pytesseract,
        "image_to_data",
        lambda *a, **k: {"text": ["99.26 p."], "conf": [93]},
    )
    monkeypatch.setattr(
        seat_evidence,
        "polarity_currency_amount",
        lambda *a: {"value": other, "readings": [{"value": other}]},
    )
    crop = np.zeros((34, 166, 3), np.uint8)
    result = seat_evidence.stack_pixels(crop.shape, crop.tobytes())
    assert result["value"] == expected
    if expected is None:
        assert result["original"]["value"] == 99.26
        assert result["rejection"] == "conflicting_stack_amounts"
    seat_evidence.stack_pixels.cache_clear()


def test_recorded_59_cannot_be_confirmed_as_99():
    path = Path("artifacts/hud/sessions/session_20261014_043822_c8a6cc/requests/00000164.png")
    if not path.exists():
        pytest.skip("Local diagnostic source unavailable")
    configure_ocr()
    crop = cv2.imread(str(path))[891:925, 555:721]
    reading = seat_evidence.stack_pixels(crop.shape, crop.tobytes())
    assert reading["value"] is None
    assert reading["original"]["value"] == 99.26
    assert reading["conflicting_values"] == [59.26]


def test_recorded_repeated_wrong_amount_does_not_survive_pair_confirmation():
    root = Path("artifacts/hud/sessions/session_20261014_043822_c8a6cc")
    if not (root / "events.jsonl").exists():
        pytest.skip("Local diagnostic source unavailable")
    rows = sorted(
        [
            r
            for line in (root / "events.jsonl").read_text(encoding="utf-8").splitlines()
            if (r := json.loads(line))["kind"] == "names" and r["frame_id"] in (159, 164)
        ],
        key=lambda r: r["frame_id"],
    )
    assert len(rows) == 2
    before, after = seat_evidence.ConfirmedStacks(), seat_evidence.ConfirmedStacks()
    configure_ocr()
    for row in rows:
        old = row["context"]["stack_readings"]["6"]
        previous_fact = before.update(row, {6: old})
        x, y, w, h = old["roi"]
        image = cv2.imread(str(saved_frame_path(root, row["frame_id"])))
        crop = image[y : y + h, x : x + w]
        fresh = {**seat_evidence.stack_pixels(crop.shape, crop.tobytes()), "roi": old["roi"]}
        assert not after.update(row, {6: fresh})
    assert previous_fact[6]["value"] == 99.26
