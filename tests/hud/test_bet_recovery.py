import json
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import pytest

from poker.hud import table_signals
from poker.hud.recognition import configure_ocr, layout_panels


@pytest.mark.parametrize(
    "frame,seat,expected",
    [(134, 5, 2), (937, 5, 2), (987, 5, 2), (1461, 4, 1), (1461, 5, 2), (175, 5, None)],
)
def test_inner_lower_seat_amount_under_chips(frame, seat, expected):
    path = (
        Path("artifacts/hud/sessions/session_20260924_102223_ea7318/ocr_frames") / f"{frame:08}.png"
    )
    if not path.exists():
        pytest.skip("Local diagnostic image unavailable")
    configure_ocr()
    image = cv2.imread(str(path))
    reading = table_signals.read_bets(image, layout_panels(image))[seat]
    assert reading["value"] == expected
    if expected is not None:
        assert reading["position_evidence"]["value"] == expected


@pytest.mark.parametrize(
    "frame,seat,expected",
    [(108, 6, 2), (503, 1, 1), (1581, 1, 2), (547, 3, 4.73), (1634, 1, 8.51), (83, 6, None)],
)
def test_recorded_bet_labels(frame, seat, expected):
    root = Path("artifacts/hud/sessions/session_20260923_054209_82f838")
    path = root / "requests" / f"{frame:08}.png"
    if not path.exists():
        path = root / "frames" / f"{frame:08}.jpg"
    if not path.exists():
        pytest.skip("Local diagnostic image unavailable")
    configure_ocr()
    image = cv2.imread(str(path))
    assert table_signals.read_bets(image, layout_panels(image))[seat]["value"] == expected


@pytest.mark.parametrize("text", ["", "2", "+2 p.", "-2 p.", "−2 p."])
def test_bet_retry_needs_unsigned_currency(monkeypatch, text):
    def unexpected(*args):
        pytest.fail("OCR must not run without eligible currency evidence")

    monkeypatch.setattr(table_signals, "polarity_currency_amount", unexpected)
    bet = {"value": None, "text": text, "roi": [0, 0, 80, 25]}
    assert table_signals.recover_bet_polarities(np.zeros((60, 100, 3), np.uint8), bet) == bet


def test_bet_recovery_preserves_strong_numeric_conflict(monkeypatch):
    monkeypatch.setattr(
        table_signals,
        "polarity_currency_amount",
        lambda *args: {"value": 2, "readings": [{"value": 2, "text": "2 p."}] * 2},
    )
    bet = {
        "value": None,
        "text": "3 p.",
        "roi": [0, 0, 80, 25],
        "words": [{"text": "3", "confidence": 95}],
    }
    reading = table_signals.recover_bet_polarities(np.zeros((60, 100, 3), np.uint8), bet)
    assert reading["value"] is None
    assert reading["polarity_evidence"]["conflicting_values"] == [3]


def test_known_bet_remains_untouched():
    bet = {"value": 12.34}
    assert table_signals.recover_bet_polarities(None, bet) is bet


def cross_attempt(roi, value=4, inverted=False, confidence=90, text="4 p."):
    return {
        "roi": roi,
        "readings": [dict(value=value, inverted=inverted, confidence=confidence, text=text)],
    }


def test_cross_region_consensus_needs_full_width_both_polarities_and_no_conflict():
    full, narrow = [10, 10, 80, 30], [30, 10, 40, 30]
    attempts = [cross_attempt(full), cross_attempt(narrow, inverted=True)]
    result = table_signals.cross_roi_currency_consensus(attempts, full)
    assert result["value"] == 4
    assert len(result["support"]) == 2
    assert table_signals.cross_roi_currency_consensus(attempts, full, [5]) is None


@pytest.mark.parametrize(
    "change", ["same_roi", "same_polarity", "weak", "conflict", "narrow_only", "signed"]
)
def test_cross_region_consensus_rejects_incomplete_or_conflicting_support(change):
    full, narrow = [10, 10, 80, 30], [30, 10, 40, 30]
    attempts = [cross_attempt(full), cross_attempt(narrow, inverted=True)]
    if change == "same_roi":
        attempts[1]["roi"] = full
    elif change == "same_polarity":
        attempts[1]["readings"][0]["inverted"] = False
    elif change == "weak":
        attempts[1]["readings"][0]["confidence"] = 84
    elif change == "conflict":
        attempts[1]["readings"][0]["value"] = 5
    elif change == "narrow_only":
        attempts[0]["roi"] = [20, 10, 50, 30]
    elif change == "signed":
        attempts.append(cross_attempt(full, None, text="-4 p."))
    assert table_signals.cross_roi_currency_consensus(attempts, full) is None


def test_recorded_hero_bet_has_agreement_across_full_and_glyph_regions():
    path = Path("artifacts/hud/sessions/session_20261005_122501_a8209d/ocr_frames/00000837.png")
    if not path.exists():
        pytest.skip("Local diagnostic image unavailable")
    configure_ocr()
    image = cv2.imread(str(path))
    reading = table_signals.read_bets(image, layout_panels(image))[6]
    assert reading["value"] == 4
    assert reading["polarity_evidence"]["cross_roi_consensus"]["value"] == 4


def test_recovered_bet_preserves_causal_pair_but_never_bridges_missing_reading():
    from poker.hud.live_evidence import LiveEvidence

    path = Path(
        "artifacts/advisor/dense_requests_20261012/fresh_stacks/2880026452_observations.jsonl"
    )
    image_path = Path(
        "artifacts/hud/sessions/session_20261005_122501_a8209d/ocr_frames/00000837.png"
    )
    if not path.exists() or not image_path.exists():
        pytest.skip("Local diagnostic recording unavailable")
    configure_ocr()
    image = cv2.imread(str(image_path))
    recovered = table_signals.read_bets(image, layout_panels(image))[6]
    live = LiveEvidence()
    results = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        item = json.loads(line)
        frame = item["frame_id"]
        if frame > 842:
            break
        slot = item["context"]["table_signals"]["slots"][6]
        if frame == 837:
            slot.update(current_bet=recovered["value"], bet_evidence=recovered)
        if frame == 841:
            # A later missing reading must invalidate even this recovered pair.
            slot.update(current_bet=None, bet_evidence={"value": None})
        item["evidence_epoch"] = live.epoch
        facts = live.update(
            item["context"],
            {k: v for k, v in item.items() if k != "context"},
            now=datetime.fromisoformat(item["captured_at"]),
        )
        if frame in (837, 839, 841, 842):
            results[frame] = facts["bet_confirmations"].get(6)
    for frame, pair in ((837, [836, 837]), (839, [837, 839])):
        assert results[frame]["value"] == 4
        assert [s["frame_id"] for s in results[frame]["confirmation_frames"]] == pair
    assert results[841] is None
    assert results[842] is None
