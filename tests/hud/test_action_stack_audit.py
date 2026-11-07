import json
from pathlib import Path

import pytest

from poker.hud.action_stack_audit import audit_action_stacks
from poker.hud.hand_reconstruction import HandReconstructor
from tests.hud.test_hand_reconstruction import row


def sample(n, stack, action=None):
    result = row(n, action=action)
    result["context"]["stack_readings"] = {"0": {"value": stack}}
    return result


def hand(rows):
    return [
        {
            "hand_id": "12345678",
            "events": [
                dict(
                    kind="action_label",
                    action="call",
                    seat_index=0,
                    frame_id=r["frame_id"],
                    captured_at=r["captured_at"],
                )
                for r in rows
                if r.get("context", {})
                .get("table_signals", {})
                .get("slots", [{}])[0]
                .get("action_label")
            ],
        }
    ]


def test_stack_drop_around_call_is_not_promoted_to_verified_action_amount():
    rows = [sample(1, 10), sample(2, 10), sample(3, None, "call"), sample(4, 8), sample(5, 8)]
    for r in rows[3:]:
        r["context"]["decision_hand"]["board"] = ["Ah", "2c", "3s"]
    (result,) = audit_action_stacks(rows, hand(rows))
    assert result["stack_decrease"] == 200
    assert result["contributed_delta"] is None and result["hand_contribution"] is None
    assert result["uses_later_evidence"] and not result["verified_for_training"]
    assert result["after"]["confirmation_frames"][0]["board"] == ["Ah", "2c", "3s"]
    assert result["confirmation_timing"] == {
        "last_evidence_captured_at": rows[-1]["captured_at"],
        "capture_span_after_action_ms": 2000,
        "before_evidence_age_ms": 1000,
        "processing_latency_ms": None,
    }
    assert audit_action_stacks(rows[:-1], hand(rows[:-1])) == []


@pytest.mark.parametrize(
    "boundary", ["pause", "hand", "window", "epoch", "settlement", "missing", "duplicate"]
)
def test_incomplete_or_incompatible_endpoints_are_not_linked(boundary):
    rows = [sample(1, 10), sample(2, 10), sample(3, None, "call"), sample(4, 8), sample(5, 8)]
    if boundary == "pause":
        rows.insert(3, {"kind": "pause"})
    elif boundary == "missing":
        rows[-1]["context"]["stack_readings"]["0"]["value"] = None
    elif boundary == "duplicate":
        rows[-1] = rows[-2]
    else:
        for r in rows[3:]:
            if boundary == "hand":
                r["context"]["hand_id"]["value"] = "87654321"
            elif boundary == "settlement":
                r["context"]["table_signals"]["slots"][0]["settlement_label"] = {"text": "wins"}
            elif boundary == "window":
                r["window"] = "other"
            else:
                r["evidence_epoch"] = 2
    assert audit_action_stacks(rows, hand(rows)) == []


def test_two_observed_money_actions_make_attribution_ambiguous():
    rows = [
        sample(1, 10),
        sample(2, 10),
        sample(3, None, "call"),
        sample(4, None, "call"),
        sample(5, 6),
        sample(6, 6),
    ]
    results = audit_action_stacks(rows, hand(rows))
    assert len(results) == 2
    assert all(
        r["status"] == "competing_actions" and r["contributed_delta"] is None for r in results
    )


def test_recorded_three_calls_have_two_ruble_stack_changes():
    path = Path("artifacts/advisor/client_history_2880027230/replay/observations_after.jsonl")
    if not path.is_file():
        pytest.skip("Local replay unavailable")
    rows = [json.loads(line) for line in path.read_text(encoding="utf8").splitlines()]
    tracker = HandReconstructor()
    for r in rows:
        tracker.update(r)
    results = audit_action_stacks(rows, list(tracker.hands.values()))
    assert [(r["action"]["frame_id"], r["stack_decrease"]) for r in results] == [
        (1035, 400),
        (1053, 200),
        (1066, 200),
        (1081, 200),
        (1098, 200),
        (1121, 200),
        (1131, 200),
        (1159, 4414),
    ]
    calls = [r for r in results if r["action"]["action"] == "call"]
    assert [(r["action"]["frame_id"], r["stack_decrease"]) for r in calls] == [
        (1053, 200),
        (1081, 200),
        (1121, 200),
    ]
    assert all(r["status"] == "observed_stack_change" for r in calls)
