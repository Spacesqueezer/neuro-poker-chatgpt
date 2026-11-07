import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import pytest

from poker.hud.bet_bridge import BetBridge
from poker.hud.live_evidence import LiveEvidence
from poker.hud.raise_minimum import MinimumRoundTrip, bridge_minimum
from poker.hud.slider import EndpointConfirmation
from tests.hud.test_confirmed_bets import row


def sample(n, side="left", value=10):
    item = row(n)
    item["evidence_epoch"] = 1
    context = item["context"]
    context["decision_hand"].update(valid=True, my_turn=True, hero=["Ah", "Kd"])
    action = "all_in" if side == "right" else "raise"
    context["table_signals"].update(
        controls={
            "flags": {"can_" + action: True},
            "call_amount": 4,
            "selected_wager": {"action": action, "value": value},
        },
        slider_evidence={"endpoint": side, "field": {"value": value}},
    )
    return item


def run(rows):
    tracker, endpoint = MinimumRoundTrip(), EndpointConfirmation()
    results = []
    for item in rows:
        ctx = item["context"]
        signals = ctx["table_signals"]
        proof = endpoint.update(
            {**item, "controls": signals["controls"], "board_cards": ctx["decision_hand"]["board"]},
            ctx["hand_id"],
            signals["slider_evidence"],
        )
        results.append(tracker.update(item, proof))
    return results


def cycle():
    return [
        sample(1),
        sample(2),
        sample(3, "right", 192),
        sample(4, "right", 192),
        sample(5),
        sample(6),
    ]


def test_full_cycle_needs_two_distinct_frames_at_each_endpoint():
    results = run(cycle())
    assert results[:5] == [None] * 5
    proof = results[-1]
    assert proof["value"] == 10
    assert proof["right_endpoint"]["value"] == 192
    assert [s["frame_id"] for s in proof["initial_left"]] == [1, 2]
    assert [s["frame_id"] for s in proof["confirmation_frames"]] == [5, 6]
    facts = {"min_raise_confirmation": proof, "participation_evidence": {}}
    payload = LiveEvidence.apply({"players": []}, facts)
    assert payload["min_raise_amount"] == 10
    assert payload["max_raise_amount"] is None


@pytest.mark.parametrize(
    "change",
    [
        "call",
        "board",
        "hero",
        "hand",
        "epoch",
        "window",
        "geometry",
        "turn",
        "invalid",
        "field",
        "disabled",
        "different_left",
        "right_not_allin",
        "right_too_small",
        "duplicate",
        "gap",
        "future",
    ],
)
def test_broken_continuity_cannot_produce_minimum(change):
    rows = cycle()
    item = rows[4]
    ctx = item["context"]
    controls = ctx["table_signals"]["controls"]
    if change == "call":
        controls["call_amount"] = 8
    elif change in ("board", "hero"):
        ctx["decision_hand"][change] = ["2c", "3c", "4c"]
    elif change == "hand":
        ctx["hand_id"]["value"] = "87654321"
    elif change == "epoch":
        item["evidence_epoch"] = 2
    elif change == "window":
        item["window"] = "other"
    elif change == "geometry":
        item["client_rect"][0] = 3
    elif change == "turn":
        ctx["decision_hand"]["my_turn"] = False
    elif change == "invalid":
        ctx["decision_hand"]["valid"] = False
    elif change == "field":
        ctx["table_signals"]["slider_evidence"]["field"]["value"] = None
    elif change == "disabled":
        controls["flags"]["can_raise"] = False
    elif change == "different_left":
        rows[4:] = [sample(5, value=12), sample(6, value=12)]
    elif change == "right_not_allin":
        for r in rows[2:4]:
            r["context"]["table_signals"]["controls"]["selected_wager"]["action"] = "raise"
    elif change == "right_too_small":
        rows[2:4] = [sample(3, "right", 8), sample(4, "right", 8)]
    elif change == "duplicate":
        rows[5] = deepcopy(rows[4])
    elif change == "gap":
        rows[4:] = [sample(20), sample(21)]
    elif change == "future":
        rows[4:] = [sample(3), sample(4)]
    assert not any(run(rows))


def test_left_alone_is_not_minimum_and_proof_expires():
    assert not any(run([sample(n) for n in range(1, 10)]))
    rows = cycle() + [sample(n) for n in range(7, 40)]
    assert run(rows)[-1] is None


def test_fast_proof_requires_fresh_matching_independent_text_frame():
    previous = sample(6)
    previous["evidence"] = {"min_raise_confirmation": run(cycle())[-1]}
    assert bridge_minimum(sample(7), previous)["value"] == 10
    assert bridge_minimum(sample(6), previous) is None
    assert bridge_minimum(sample(9), previous) is None
    assert bridge_minimum(sample(7, value=12), previous) is None
    previous["evidence"]["min_raise_confirmation"]["initial_left"][0]["captured_at"] = row(-25)[
        "captured_at"
    ]
    assert bridge_minimum(sample(7), previous) is None


def test_live_tracker_resets_cycle():
    tracker = LiveEvidence()
    results = []
    for item in cycle():
        if item["frame_id"] == 5:
            tracker.reset()
            tracker.epoch = 1
        meta = {k: v for k, v in item.items() if k != "context"}
        facts = tracker.update(
            item["context"], meta, now=datetime.fromisoformat(item["captured_at"])
        )
        results.append(facts["min_raise_confirmation"])
    assert not any(results)


def test_recorded_fast_round_trip_confirms_only_after_return():
    root = Path("artifacts/hud/sessions/session_20261005_122501_a8209d")
    if not root.exists():
        pytest.skip("Local session is unavailable")
    events = sorted(
        [
            json.loads(line)
            for path in root.glob("events.jsonl*")
            for line in path.read_text(encoding="utf8").splitlines()
        ],
        key=lambda e: e["at"],
    )
    tracker = LiveEvidence()
    confirmed = []
    for e in events:
        if e["kind"] != "fast_table" or not e["accepted"]:
            continue
        if tracker.epoch != e["evidence_epoch"]:
            tracker.reset()
            tracker.epoch = e["evidence_epoch"]
        meta = {
            k: e[k] for k in ("frame_id", "captured_at", "window", "client_rect", "evidence_epoch")
        }
        facts = tracker.update(e["context"], meta, now=datetime.fromisoformat(e["at"]))
        if facts and facts["min_raise_confirmation"]:
            confirmed.append((e["frame_id"], facts["min_raise_confirmation"]["value"]))
    assert confirmed == [(343, 10.0), (348, 10.0)]


def test_recorded_text_request_keeps_both_bounds_after_round_trip():
    root = Path("artifacts/hud/sessions/session_20261005_122501_a8209d")
    if not root.exists():
        pytest.skip("Local session is unavailable")
    events = sorted(
        [
            json.loads(line)
            for path in root.glob("events.jsonl*")
            for line in path.read_text(encoding="utf8").splitlines()
        ],
        key=lambda e: e["at"],
    )
    names = {e["frame_id"]: e for e in events if e["kind"] == "names"}
    fast, text, bridge = LiveEvidence(), LiveEvidence(), BetBridge()
    result = None
    for e in events:
        kind = e["kind"]
        if kind in ("window", "target", "pause", "fast_table_error"):
            bridge.rows.clear()
        if kind not in ("fast_table", "live_evidence"):
            continue
        if kind == "fast_table" and not e["accepted"]:
            bridge.rows.clear()
            continue
        tracker = fast if kind == "fast_table" else text
        if tracker.epoch != e["evidence_epoch"]:
            tracker.reset()
            tracker.epoch = e["evidence_epoch"]
        ctx = e["context"] if kind == "fast_table" else names[e["frame_id"]]["context"]
        meta = {
            k: e[k] for k in ("frame_id", "captured_at", "window", "client_rect", "evidence_epoch")
        }
        meta["image"] = str(root / "ocr_frames" / f"{e['frame_id']:08d}.png")
        facts = tracker.update(ctx, meta, now=datetime.fromisoformat(e["at"]))
        if facts is None:
            continue
        if kind == "fast_table":
            bridge.add(meta, ctx, facts)
        else:
            facts = bridge.augment(meta, ctx, facts)
            if e["frame_id"] == 347:
                result = LiveEvidence.apply({"players": []}, facts)
                break
    assert result is not None
    assert result["min_raise_amount"] == 10
    assert result["max_raise_amount"] == 192
