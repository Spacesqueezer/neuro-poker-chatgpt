from copy import deepcopy

import pytest

from poker.hud.live_evidence import LiveEvidence
from poker.hud.raise_cap import confirmed_raise_cap, refresh_round_trip_cap
from tests.hud.test_confirmed_bets import row


def refreshed_setup():
    current, old, facts = setup()
    cap = confirmed_raise_cap(current, old, facts)
    previous = {**deepcopy(current), "max_raise_confirmation": cap}
    current.update({k: row(7)[k] for k in ("frame_id", "captured_at", "image")})
    signals = current["context"]["table_signals"]
    signals["controls"].update(
        flags={"can_raise": True}, selected_wager={"action": "raise", "value": 4}
    )
    signals["slider_evidence"] = {"endpoint": "left", "field": {"value": 4}}
    facts["min_raise_confirmation"] = {
        "value": 4,
        "right_endpoint": {"value": 102, "confirmation_frames": cap["confirmation_frames"][:2]},
    }
    for key in ("stack_confirmations", "bet_confirmations"):
        facts[key][6]["confirmation_frames"] = [
            {k: row(n)[k] for k in ("frame_id", "captured_at", "image")} for n in (6, 7)
        ]
    return current, previous, facts


def test_cap_after_return_requires_fresh_unchanged_hero_amounts():
    current, previous, facts = refreshed_setup()
    proof = refresh_round_trip_cap(current, previous, facts)
    assert proof["value"] == 102
    assert proof["revalidated_at"]["frame_id"] == 7
    assert [s["frame_id"] for s in proof["confirmation_frames"]] == [1, 2, 3]


@pytest.mark.parametrize(
    "change",
    [
        "no_minimum",
        "other_visit",
        "call",
        "hand",
        "stack",
        "bet",
        "old_amounts",
        "duplicate_amounts",
        "future",
        "expired",
    ],
)
def test_cap_does_not_leak_outside_verified_cycle(change):
    current, previous, facts = refreshed_setup()
    if change == "no_minimum":
        facts.pop("min_raise_confirmation")
    elif change == "other_visit":
        facts["min_raise_confirmation"]["right_endpoint"]["confirmation_frames"] = [
            {"frame_id": 99}
        ]
    elif change == "call":
        current["context"]["table_signals"]["controls"]["call_amount"] = 2
    elif change == "hand":
        current["context"]["hand_id"]["value"] = "87654321"
    elif change == "stack":
        facts["stack_confirmations"][6]["value"] = 98
    elif change == "bet":
        facts["bet_confirmations"].clear()
    elif change == "old_amounts":
        facts["stack_confirmations"][6]["confirmation_frames"][0]["captured_at"] = row(1)[
            "captured_at"
        ]
    elif change == "duplicate_amounts":
        facts["stack_confirmations"][6]["confirmation_frames"][0]["frame_id"] = 7
    elif change == "future":
        current["captured_at"] = row(2)["captured_at"]
    elif change == "expired":
        current["captured_at"] = row(40)["captured_at"]
    assert refresh_round_trip_cap(current, previous, facts) is None


def setup():
    old, current = row(2), row(3)
    for item in (old, current):
        item["evidence_epoch"] = 1
        item["context"]["decision_hand"] = {
            "valid": True,
            "my_turn": True,
            "hero": ["Ah", "Kd"],
            "board": [],
        }
        item["context"]["table_signals"].update(
            controls={
                "flags": {"can_all_in": True},
                "call_amount": 0,
                "selected_wager": {"action": "all_in", "value": 102},
            },
            slider_evidence={"endpoint": "right", "field": {"value": 102}},
        )

    def source(n):
        return {k: row(n)[k] for k in ("frame_id", "captured_at", "image")}

    old["evidence"] = {
        "slider_endpoint": {
            "endpoint": "right",
            "value": 102,
            "hand_id": "12345678",
            "confirmation_frames": [source(1), source(2)],
        }
    }
    facts = {
        "hand_id": "12345678",
        "stack_confirmations": {6: {"value": 100, "confirmation_frames": [source(2), source(3)]}},
        "bet_confirmations": {6: {"value": 2, "confirmation_frames": [source(2), source(3)]}},
    }
    return current, old, facts


def test_confirmed_cap_is_total_including_posted_bet():
    current, old, facts = setup()
    cap = confirmed_raise_cap(current, old, facts)
    assert cap["value"] == 102
    assert cap["semantics"] == "street_total_including_current_bet"
    assert [s["frame_id"] for s in cap["confirmation_frames"]] == [1, 2, 3]
    facts.update(max_raise_confirmation=cap, participation_evidence={})
    payload = LiveEvidence.apply({"players": [], "min_raise_amount": None}, facts)
    assert payload["max_raise_amount"] == 102
    assert payload["min_raise_amount"] is None


@pytest.mark.parametrize(
    "change",
    [
        "left",
        "interior",
        "call",
        "not_all_in",
        "field",
        "stack",
        "missing_bet",
        "hand",
        "street",
        "epoch",
        "geometry",
        "not_turn",
        "future",
        "stale",
        "duplicate",
        "stale_stack",
        "single_stack",
    ],
)
def test_cap_requires_all_independent_current_sources(change):
    current, old, facts = setup()
    signals = current["context"]["table_signals"]
    if change in ("left", "interior"):
        signals["slider_evidence"]["endpoint"] = change
    if change == "call":
        signals["controls"]["call_amount"] = 4
    if change == "not_all_in":
        signals["controls"]["selected_wager"]["action"] = "raise"
    if change == "field":
        signals["slider_evidence"]["field"]["value"] = 100
    if change == "stack":
        facts["stack_confirmations"][6]["value"] = 99
    if change == "missing_bet":
        facts["bet_confirmations"] = {}
    if change == "hand":
        current["context"]["hand_id"]["value"] = "87654321"
    if change == "street":
        current["context"]["decision_hand"]["board"] = ["2s", "3s", "4s"]
    if change == "epoch":
        current["evidence_epoch"] = 2
    if change == "geometry":
        current["client_rect"][0] = 20
    if change == "not_turn":
        current["context"]["decision_hand"]["my_turn"] = False
    if change == "future":
        old["captured_at"] = row(4)["captured_at"]
    if change == "stale":
        current["captured_at"] = row(9)["captured_at"]
    if change == "duplicate":
        old["evidence"]["slider_endpoint"]["confirmation_frames"][0] = deepcopy(
            old["evidence"]["slider_endpoint"]["confirmation_frames"][1]
        )
    if change == "stale_stack":
        facts["stack_confirmations"][6]["confirmation_frames"][-1]["frame_id"] = 1
    if change == "single_stack":
        facts["stack_confirmations"][6]["confirmation_frames"].pop(0)
    assert confirmed_raise_cap(current, old, facts) is None
