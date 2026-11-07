from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import cv2
import pytest

from poker.hud.recognition import configure_ocr, layout_panels
from poker.hud.seat_evidence import ConfirmedStacks, participation, read_stack


def row(n, hand="12345678"):
    return {
        "frame_id": n,
        "captured_at": (datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=n)).isoformat(),
        "window": "table",
        "client_rect": [0, 0, 1000, 800],
        "context": {"hand_id": {"value": hand, "confidence": 95}},
    }


def reading(value, confidence=96):
    return {0: {"value": value, "confidence": confidence}}


def test_stacks_need_two_fresh_distinct_frames_and_never_carry_across_hands():
    tracker = ConfirmedStacks()
    assert not tracker.update(row(1), reading(100))
    assert not tracker.update(row(1), reading(100))
    assert tracker.update(row(2), reading(100))[0]["value"] == 100
    assert not tracker.update(row(3), reading(None))
    assert not tracker.update(row(4), reading(100))
    assert not tracker.update(row(12), reading(100))
    assert tracker.update(row(13), reading(100))[0]["value"] == 100
    assert not tracker.update(row(14, "87654321"), reading(100))
    assert not tracker.update(row(15, "87654321"), reading(100, 84))


def test_unknown_and_fold_are_distinct_and_no_future_participation():
    tracker = SimpleNamespace(current=None)
    assert participation(tracker) == {}
    tracker.current = {
        "participants": {
            "2": {"fold_observed": False, "evidence": [{"kind": "repeated_card_backs"}]}
        },
        "warnings": [],
    }
    tracker.presence = {2: (None, [])}
    assert participation(tracker)[2] == {
        "cards_dealt": True,
        "is_active": None,
        "evidence": [{"kind": "repeated_card_backs"}],
    }
    tracker.presence = {2: ("card_backs", [{}, {}])}
    assert participation(tracker)[2]["is_active"] is True
    tracker.current["participants"]["2"]["fold_observed"] = True
    assert participation(tracker)[2]["is_active"] is False
    tracker.current["warnings"] = ["action_after_fold"]
    assert participation(tracker)[2]["is_active"] is None


@pytest.mark.parametrize("seat,value", [(6, 198), (1, 222.69)])
def test_stack_reader_on_recorded_preflop(seat, value):
    path = (
        Path(__file__).resolve().parents[2]
        / "artifacts/hud/sessions/session_20260911_020140_b8974b/frames/00000084.jpg"
    )
    if not path.exists():
        pytest.skip("Local recorded image unavailable")
    configure_ocr()
    frame = cv2.imread(str(path))
    result = read_stack(frame, layout_panels(frame)[seat])
    assert result["value"] == value
    assert result["confidence"] >= 85


def test_out_of_order_or_duplicate_stack_reading_cannot_replace_evidence():
    tracker = ConfirmedStacks()
    tracker.update(row(2), reading(100))
    assert not tracker.update(row(1), reading(999))
    assert not tracker.update(row(2), reading(999))
    result = tracker.update(row(3), reading(100))
    assert [r["frame_id"] for r in result[0]["confirmation_frames"]] == [2, 3]


def test_action_label_alone_does_not_prove_dealt_cards():
    tracker = SimpleNamespace(
        current={
            "participants": {"0": {"fold_observed": True, "evidence": [{"kind": "action_label"}]}},
            "warnings": [],
        },
        presence={},
    )
    assert participation(tracker) == {}


def test_sitting_out_label_is_not_a_zero_stack():
    path = (
        Path(__file__).resolve().parents[2]
        / "artifacts/hud/sessions/session_20260912_074919_b1e521/frames/00000023.jpg"
    )
    if not path.exists():
        pytest.skip("Local new session unavailable")
    configure_ocr()
    frame = cv2.imread(str(path))
    result = read_stack(frame, layout_panels(frame)[2])
    assert result["value"] is None
    assert result["seat_status"]["status"] == "sitting_out"


def test_past_fold_and_missing_stack_do_not_prove_current_occupancy():
    from poker.hud.seat_evidence import occupancy_evidence

    assert (
        occupancy_evidence({0: {"is_active": False, "cards_dealt": True}}, {}, {0: {"value": None}})
        == {}
    )
    assert occupancy_evidence({0: {"is_active": True}}, {}, {})[0]["occupied"] is True
    assert occupancy_evidence({}, {1: {"value": 0}}, {})[1]["occupied"] is True
    status = {2: {"seat_status": {"status": "sitting_out", "words": [{"confidence": 96}]}}}
    assert occupancy_evidence({}, {}, status)[2]["occupied"] is True
    status[2]["seat_status"]["words"][0]["confidence"] = 84
    assert occupancy_evidence({}, {}, status) == {}


@pytest.mark.parametrize("before,after", [(1, 2), (None, 1), (1, None)])
def test_stack_confirmation_does_not_bridge_capture_epochs(before, after):
    tracker = ConfirmedStacks()
    assert not tracker.update({**row(1), "evidence_epoch": before}, reading(100))
    assert not tracker.update({**row(2), "evidence_epoch": after}, reading(100))
    result = tracker.update({**row(3), "evidence_epoch": after}, reading(100))
    frames = result[0]["confirmation_frames"]
    assert [f["frame_id"] for f in frames] == [2, 3]
    assert all(f["evidence_epoch"] == after for f in frames)
