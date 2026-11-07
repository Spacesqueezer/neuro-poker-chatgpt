from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest

from poker.hud.hand_reconstruction import HandReconstructor
from poker.hud.seat_evidence import confirmed_bets


def row(number, value=2):
    return {
        "frame_id": number,
        "captured_at": (datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=number)).isoformat(),
        "window": "table",
        "client_rect": [0, 0, 1200, 1000],
        "image": f"{number}.jpg",
        "context": {
            "hand_id": {"value": "12345678", "confidence": 95},
            "hero_visible": True,
            "decision_hand": {"board": []},
            "table_signals": {
                "slots": [
                    {
                        "seat_index": i,
                        "roi": [i * 100, 200, 100, 40],
                        "current_bet": value if i == 0 else None,
                        "bet_evidence": {"value": value if i == 0 else None, "text": "2 p."},
                    }
                    for i in range(7)
                ]
            },
        },
    }


def ready():
    tracker = HandReconstructor()
    for n in (1, 2, 3):
        tracker.update(row(n))
    return tracker


def test_bet_uses_two_exact_sources_and_never_fills_missing_with_zero():
    tracker = ready()
    facts = confirmed_bets(row(3), row(2), tracker)
    assert set(facts) == {0}
    assert facts[0]["value"] == 2
    assert [s["frame_id"] for s in facts[0]["confirmation_frames"]] == [2, 3]
    assert facts[0]["semantics"] == "visible_street_contribution_not_action_size"


@pytest.mark.parametrize(
    "change",
    [
        "amount",
        "missing",
        "payout",
        "evidence",
        "roi",
        "window",
        "hand",
        "board",
        "gap",
        "duplicate",
        "out_of_order",
    ],
)
def test_bet_confirmation_rejects_discontinuity_and_conflicting_sources(change):
    tracker = ready()
    previous, current = row(2), row(3)
    slot = previous["context"]["table_signals"]["slots"][0]
    if change == "amount":
        slot["current_bet"] = 4
    if change == "missing":
        slot["current_bet"] = None
    if change == "payout":
        slot["settlement_label"] = {"text": "won"}
    if change == "evidence":
        slot["bet_evidence"]["value"] = 4
    if change == "roi":
        slot["roi"][0] += 5
    if change == "window":
        previous["window"] = "other"
    if change == "hand":
        previous["context"]["hand_id"]["value"] = "99999999"
    if change == "board":
        previous["context"]["decision_hand"]["board"] = ["Ah", "Ks", "2d"]
    if change == "gap":
        previous["captured_at"] = row(-10)["captured_at"]
    if change == "duplicate":
        previous = deepcopy(current)
    if change == "out_of_order":
        previous = row(4)
    assert confirmed_bets(current, previous, tracker) == {}


def test_changed_bet_waits_for_repeat_and_unknown_street_blocks():
    tracker = ready()
    current = row(4, 6)
    tracker.update(current)
    assert not confirmed_bets(current, row(3), tracker)
    next_row = row(5, 6)
    tracker.update(next_row)
    assert confirmed_bets(next_row, current, tracker)[0]["value"] == 6
    tracker.interrupt("capture_boundary")
    assert not confirmed_bets(next_row, current, tracker)


def test_boolean_is_not_a_previous_numeric_bet():
    tracker = ready()
    assert not confirmed_bets(row(3, 1), row(2, True), tracker)
