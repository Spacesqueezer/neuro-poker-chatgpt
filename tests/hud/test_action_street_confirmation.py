from copy import deepcopy

import pytest

from poker.hud.hand_reconstruction import HandReconstructor
from tests.hud.test_hand_reconstruction import events, row

TURN = ("4d", "7h", "7d", "Qs")
RIVER = (*TURN, "8c")


def ready():
    tracker = HandReconstructor()
    for n in (1, 2, 3):
        tracker.update(row(n, board=TURN))
    return tracker


def test_first_river_check_gets_street_only_after_identical_board_confirmation():
    tracker = ready()
    tracker.update(row(4, board=RIVER, action="check"))
    prefix = deepcopy(events(tracker, "action_label"))
    assert prefix[0]["street"] is None
    tracker.update(row(5, board=RIVER, action="check"))
    (action,) = events(tracker, "action_label")
    assert action["street"] == "river" and action["frame_id"] == 4
    assert [s["frame_id"] for s in action["street_confirmation_frames"]] == [4, 5]
    assert prefix[0]["street"] is None


@pytest.mark.parametrize("interruption", ["different_card", "unknown_card", "pause", "gap"])
def test_no_retroactive_street_assignment_across_uncertainty(interruption):
    tracker = ready()
    tracker.update(row(4, board=RIVER, action="check"))
    if interruption == "pause":
        tracker.interrupt("capture_boundary")
    elif interruption == "gap":
        tracker.update(row(10, board=RIVER, action="check"))
    else:
        tracker.update(row(5, board=(*TURN, "8h" if interruption == "different_card" else "")))
    tracker.update(row(11, board=RIVER))
    tracker.update(row(12, board=RIVER))
    action = events(tracker, "action_label")[0]
    assert action["street"] is None
    assert "street_confirmation_frames" not in action


def test_action_on_incomplete_board_is_not_repaired_from_future_cards():
    tracker = ready()
    tracker.update(row(4, board=(*TURN, ""), action="fold"))
    tracker.update(row(5, board=RIVER, action="fold"))
    tracker.update(row(6, board=RIVER, action="fold"))
    (action,) = events(tracker, "action_label")
    assert action["street"] is None


def test_fresh_confirmed_river_labels_fold_without_repairing_cards_or_amounts():
    tracker = ready()
    for n in (4, 5):
        tracker.update(row(n, board=RIVER))
    partial = ("4d", "7h", "7d", "", "8c")
    tracker.update(row(6, board=partial, action="fold", bet=2))
    (action,) = events(tracker, "action_label")
    assert action["street"] == "river"
    assert action["street_context"]["observed_board"] == list(partial)
    assert action["street_context"]["previous_source"]["frame_id"] == 5
    assert tracker.street is None
    assert not events(tracker, "bet_amount")


@pytest.mark.parametrize("case", ["conflict", "two_missing", "stale", "pause", "new_hand"])
def test_partial_river_cannot_bridge_conflicts_or_stale_context(case):
    tracker = ready()
    for n in (4, 5):
        tracker.update(row(n, board=RIVER))
    partial = ["4d", "7h", "7d", "", "8c"]
    if case == "conflict":
        partial[0] = "4s"
    elif case == "two_missing":
        partial[1] = ""
    elif case == "pause":
        tracker.interrupt("capture_boundary")
    for n in (11, 12) if case == "stale" else (6, 7):
        tracker.update(
            row(
                n,
                board=partial,
                action="fold",
                hand="87654321" if case == "new_hand" else "12345678",
            )
        )
    actions = events(tracker, "action_label")
    assert actions and all(e["street"] is None for e in actions)
