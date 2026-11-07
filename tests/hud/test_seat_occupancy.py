from datetime import UTC, datetime, timedelta
from pathlib import Path

import cv2
import numpy as np
import pytest

from poker.hud.recognition import layout_panels
from poker.hud.seat_occupancy import EmptySeatTracker, read_empty_seat


def row(n):
    return {
        "frame_id": n,
        "captured_at": (datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=n)).isoformat(),
        "window": "table",
        "client_rect": [0, 0, 1000, 800],
    }


def test_empty_needs_fresh_repeat_and_rejects_conflicts():
    tracker = EmptySeatTracker()
    reading = {0: {"empty": True}}
    assert tracker.update(row(1), reading) == {}
    assert tracker.update(row(1), reading) == {}
    assert tracker.update(row(2), reading)[0]["occupied"] is False
    assert tracker.update(row(3), reading, occupied={0}) == {}
    assert tracker.update(row(4), reading) == {}
    assert tracker.update(row(5), {}) == {}
    assert tracker.update(row(6), reading) == {}
    assert tracker.update(row(20), reading) == {}
    changed = {**row(21), "client_rect": [10, 10, 1000, 800]}
    assert tracker.update(changed, reading) == {}


@pytest.mark.parametrize(
    "number,expected",
    [(1580, [0]), (3258, [1]), (4232, [2]), (3998, [2]), (1137, [3]), (1872, []), (2684, [])],
)
def test_empty_icon_is_not_folded_or_occupied_plaque(number, expected):
    root = Path(__file__).resolve().parents[2]
    path = root / f"artifacts/hud/sessions/session_20260912_114052_d37ed0/frames/{number:08d}.jpg"
    if not path.exists():
        pytest.skip("Local recorded session unavailable")
    frame = cv2.imread(str(path))
    assert [
        i
        for i, roi in enumerate(layout_panels(frame))
        if read_empty_seat(frame, roi)["empty"] is True
    ] == expected


def test_blank_pixels_are_unknown():
    assert read_empty_seat(np.zeros((300, 400, 3), np.uint8), (50, 80, 221, 87))["empty"] is None


@pytest.mark.parametrize("number", [361, 753, 1562])
def test_empty_lower_left_icon_at_automatic_window_size(number):
    path = (
        Path("artifacts/hud/sessions/session_20261015_090831_f9d6b3/ocr_frames")
        / f"{number:08d}.png"
    )
    if not path.exists():
        pytest.skip("Local recorded session unavailable")
    frame = cv2.imread(str(path))
    # Other seats include dim/folded plaques, action captions and a zero stack.
    found = [
        i
        for i, roi in enumerate(layout_panels(frame))
        if read_empty_seat(frame, roi)["empty"] is True
    ]
    assert found == ([0, 4] if number in (361, 753) else [4])


def test_new_empty_icon_needs_two_images_before_removing_false_name():
    from poker.hud.models import PlayerObservation
    from poker.hud.seat_occupancy import clear_empty_identities
    from poker.hud.state import TableState

    root = Path("artifacts/hud/sessions/session_20261015_090831_f9d6b3/ocr_frames")
    paths = [root / f"{n:08d}.png" for n in (361, 371)]
    if not all(path.exists() for path in paths):
        pytest.skip("Local recorded session unavailable")
    tracker, state = EmptySeatTracker(), TableState()
    for index, path in enumerate(paths, 1):
        frame = cv2.imread(str(path))
        roi = layout_panels(frame)[4]
        # Preserve the raw OCR artifact; only confirmed emptiness clears its seat.
        state.update([PlayerObservation(roi, "SE", 51, "", "recognized")], (1280, 1040))
        confirmed = tracker.update(row(index), {4: read_empty_seat(frame, roi)})
        removed = clear_empty_identities(state, [{"seat_index": 4, "roi": roi}], confirmed)
        assert bool(removed) is (index == 2)
        assert bool(state.seats) is (index == 1)


@pytest.mark.parametrize("number,empty", [(368, False), (537, True), (724, True), (1244, True)])
def test_lower_empty_icon_above_plaque_on_table_rim(number, empty):
    path = (
        Path("artifacts/hud/sessions/session_20261004_094146_2c0c19/requests") / f"{number:08d}.png"
    )
    if not path.exists():
        pytest.skip("Local recorded session unavailable")
    frame = cv2.imread(str(path))
    result = read_empty_seat(frame, layout_panels(frame)[5])
    assert (result["empty"] is True) == empty
    if empty:
        assert result["search_position"] == "above_plaque"
        assert result["similarity"] >= 0.93


@pytest.mark.parametrize(
    "number,expected", [(3099, [1]), (3107, [1]), (2437, [1]), (3258, []), (1872, []), (2684, [])]
)
def test_dim_status_does_not_match_stacks_or_empty_icons(number, expected):
    from poker.hud.seat_occupancy import read_dim_status

    root = Path(__file__).resolve().parents[2]
    path = root / f"artifacts/hud/sessions/session_20260912_114052_d37ed0/frames/{number:08d}.jpg"
    if not path.exists():
        pytest.skip("Local recorded session unavailable")
    frame = cv2.imread(str(path))
    assert [
        i for i, roi in enumerate(layout_panels(frame)) if read_dim_status(frame, roi)
    ] == expected


def test_dim_status_keeps_unknown_stack_and_positive_occupancy():
    from poker.hud.recognition import configure_ocr
    from poker.hud.seat_evidence import occupancy_evidence, read_stack

    root = Path(__file__).resolve().parents[2]
    path = root / "artifacts/hud/sessions/session_20260912_114052_d37ed0/frames/00003099.jpg"
    if not path.exists():
        pytest.skip("Local recorded session unavailable")
    configure_ocr()
    frame = cv2.imread(str(path))
    reading = read_stack(frame, layout_panels(frame)[1])
    assert reading["value"] is None
    assert reading["seat_status"]["method"] == "visual_template"
    assert occupancy_evidence({}, {}, {1: reading})[1]["occupied"] is True
