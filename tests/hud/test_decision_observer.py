from concurrent.futures import Future
from copy import deepcopy
from datetime import datetime, timedelta
from unittest.mock import Mock

import numpy as np
import pytest

from poker.hud.decision_observer import fast_decision_draft
from poker.hud.decision_stream import DecisionStream
from poker.hud.hand_reconstruction import HandReconstructor
from tests.hud.test_confirmed_bets import row
from tests.hud.test_live_evidence_app import app


def observation(number=3):
    source = row(number)
    source["evidence_epoch"] = 1
    source["hero_seat"] = 6
    context = source.pop("context")
    context["hero_seat"] = 6
    context["decision_hand"] = dict(hero=["Ah", "Kd"], board=[], valid=True, my_turn=True)
    facts = {
        "hand_id": "12345678",
        "participation_evidence": {},
        "bet_confirmations": {},
        "stack_confirmations": {0: {"value": 100}},
    }
    return source, context, facts


def emit(source, context, facts, **kwargs):
    return fast_decision_draft(
        context,
        source,
        facts,
        HandReconstructor(),
        DecisionStream(),
        now=datetime.fromisoformat(source["captured_at"]),
        **kwargs,
    )


@pytest.mark.parametrize("changed", ["ended", "cards", "low_confidence", "older", "other_epoch"])
def test_newer_card_result_prevents_obsolete_decision(changed):
    source, context, facts = observation()
    latest = {**deepcopy(source), "hand": deepcopy(context["decision_hand"])}
    if changed == "cards":
        latest["hand"]["board"] = ["2h", "3h", "4h"]
    elif changed == "low_confidence":
        latest["hand"]["valid"] = False
    else:
        latest["hand"]["my_turn"] = False
    if changed == "older":
        latest["captured_at"] = row(2)["captured_at"]
    elif changed == "other_epoch":
        latest["evidence_epoch"] = 2
    draft = emit(source, context, facts, latest_cards=latest)
    if changed == "ended":
        assert draft is None
    else:
        assert draft["would_send"] is False
        assert ("newer_cards_disagree" in draft["blockers"]) == (
            changed in {"cards", "low_confidence"}
        )


def test_partial_draft_preserves_unknowns_and_never_calls_model():
    source, context, facts = observation()
    draft = emit(source, context, facts)
    players = draft["request"]["players"]
    assert players[0]["stack"] == 100
    assert players[1]["stack"] is None
    assert all(p["current_bet"] is None and p["name"] == "" for p in players)
    assert draft["decision_source"] == "fast_table"
    assert draft["model_called"] is draft["would_send"] is False
    assert "turn_continuity_unverified" in draft["blockers"]
    facts["hand_id"] = "99999999"
    assert emit(source, context, facts) is None


def test_no_turn_or_stale_source_never_produces_a_draft():
    source, context, facts = observation()
    late = datetime.fromisoformat(source["captured_at"]) + timedelta(seconds=6)
    assert (
        fast_decision_draft(context, source, facts, HandReconstructor(), DecisionStream(), now=late)
        is None
    )
    context["decision_hand"]["my_turn"] = False
    assert emit(source, context, facts) is None


def test_fast_request_does_not_wait_for_unfinished_name_future(tmp_path):
    hud = app(tmp_path)
    source, generation, _, frame = hud.names_context
    context = hud.names_future.result()[1]
    hud.names_future = Future()  # Deliberately never completed.
    hud.fast_context = source, generation, frame
    hud.fast_future = Future()
    hud.fast_future.set_result(context)
    hud.collect_fast_table()
    kinds = [c.args[0] for c in hud.recorder.event.call_args_list]
    assert "decision_dry_run" in kinds
    assert not hud.names_future.done()
    hud.stats_collector.observe.assert_not_called()


def test_name_exception_keeps_capture_epoch_fast_state_and_confirmations(tmp_path):
    hud = app(tmp_path)
    hud.names_future = Future()
    hud.names_future.set_exception(RuntimeError("slow OCR failed"))
    hud.decision_stream.count = 2
    tracker = hud.fast_evidence.tracker
    hud.collect_names()
    assert hud.capture_epoch == 1
    assert hud.fast_evidence.tracker is tracker
    assert hud.decision_stream.count == 2


@pytest.mark.parametrize("hero_turn", [True, False])
def test_parallel_reader_keeps_seat_identity_and_does_not_run_names(monkeypatch, hero_turn):
    from poker.hud import context as slow
    from poker.hud import fast_table as fast
    from poker.hud.hand import HandObservation

    rois = [(i * 100, 200, 100, 40) for i in range(7)]
    monkeypatch.setattr(slow, "analyze", Mock(side_effect=AssertionError("name OCR called")))
    monkeypatch.setattr(fast, "layout_panels", lambda _: rois)
    monkeypatch.setattr(fast, "read_hand_id", lambda _: {"value": "12345678", "confidence": 95})
    monkeypatch.setattr(fast, "find_cards", lambda _: [])
    monkeypatch.setattr(fast, "my_turn", lambda _: hero_turn)
    monkeypatch.setattr(fast, "observe", lambda *a: HandObservation(my_turn=hero_turn))
    monkeypatch.setattr(fast, "read_bet", lambda f, r, i: {"value": i})
    monkeypatch.setattr(
        fast, "read_settlement_label", lambda f, r: {"text": "win"} if r == rois[2] else None
    )
    monkeypatch.setattr(fast, "read_action_label", lambda *a: None)
    monkeypatch.setattr(fast, "card_back_pair", lambda *a: {"present": True})
    stacks = Mock(side_effect=lambda f, s: {"value": 100 + s["seat_index"]})
    monkeypatch.setattr(fast, "read_slot_stack", stacks)
    monkeypatch.setattr(fast, "read_empty_seat", lambda *a: {"empty": False})
    monkeypatch.setattr(
        fast, "decision_fields", lambda *a: ({"pot": {"value": 7}, "dealer_slot": 3}, [], 0)
    )
    result = fast.analyze_fast_table(np.zeros((800, 1000, 3), np.uint8))
    slots = result["table_signals"]["slots"]
    assert [s["seat_index"] for s in slots] == list(range(7))
    assert slots[2]["current_bet"] is None  # Payout cannot masquerade as a bet.
    if hero_turn:
        assert result["stack_readings"][5]["value"] == 105
        assert slots[3]["is_dealer"] is True
        assert stacks.call_count == 7
    else:
        assert not result["stack_readings"]
        stacks.assert_not_called()
