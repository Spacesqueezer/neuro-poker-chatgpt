import copy
import json
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from poker.hud.decision_stream import DecisionStream, request_errors
from poker.hud.diagnostics import Recorder


def payload():
    return {
        "is_my_turn": True,
        "street_name": "preflop",
        "board_cards": [],
        "hero_hole_cards": ["Ah", "As"],
        "total_pot": 15.5,
        "call_amount_needed": 2.5,
        "min_raise_amount": 5.0,
        "max_raise_amount": 100.0,
        "players": [
            {
                "seat_index": 1,
                "name": "",
                "is_active": True,
                "is_dealer": True,
                "stack": 100.0,
                "current_bet": 0.0,
                "cards_dealt": True,
            }
        ],
        "can_fold": True,
        "can_check": False,
        "can_call": True,
        "can_bet": False,
        "can_raise": True,
        "can_all_in": True,
    }


def metadata(frame=1):
    return {
        "frame_id": frame,
        "captured_at": datetime.now(UTC).isoformat(),
        "window": "test",
        "client_rect": [0, 0, 1000, 800],
    }


def test_request_contract_accepts_empty_name_but_not_unknown_game_facts():
    p = payload()
    assert request_errors(p) == []
    p["can_call"] = None
    assert "can_call_unknown" in request_errors(p)
    p = payload()
    p["hero_hole_cards"] = ["Ah", "Ah"]
    assert "cards_unknown_or_invalid" in request_errors(p)


def test_stream_two_frames_no_duplicates_and_no_false_turn_requests():
    stream = DecisionStream()
    p = payload()
    first = stream.update(p, metadata(), "2861007497", cards_valid=True)
    assert not first["would_send"]
    assert stream.update(p, metadata(), "2861007497", cards_valid=True) is None
    ready = stream.update(p, metadata(2), "2861007497", cards_valid=True)
    assert ready["would_send"]
    renamed = copy.deepcopy(p)
    renamed["players"][0]["name"] = "gh0st_"
    assert stream.update(renamed, metadata(3), "2861007497", cards_valid=True) is None
    p["is_my_turn"] = False
    assert stream.update(p, metadata(4), "2861007497", cards_valid=True) is None
    p["is_my_turn"] = True
    assert not stream.update(p, metadata(5), "2861007497", cards_valid=True)["would_send"]


@pytest.mark.parametrize("blockers,valid", [((), False), (("betting_state_unverified",), True)])
def test_repeated_uncertainty_never_becomes_ready(blockers, valid):
    stream = DecisionStream()
    for i in range(1, 5):
        result = stream.update(
            payload(), metadata(i), "2861007497", cards_valid=valid, blockers=blockers
        )
        assert result is None or not result["would_send"]


def test_uncertain_cards_do_not_count_toward_later_confident_request():
    stream = DecisionStream()
    for frame in (1, 2):
        result = stream.update(payload(), metadata(frame), "12345678", cards_valid=False)
        assert result is None or result["confirmations"] == 0
    first = stream.update(payload(), metadata(3), "12345678", cards_valid=True)
    assert first["would_send"] is False
    assert first["confirmations"] == 1
    assert "awaiting_second_frame" in first["blockers"]
    second = stream.update(payload(), metadata(4), "12345678", cards_valid=True)
    assert second["would_send"] is True
    stream.update(payload(), metadata(5), "12345678", cards_valid=False)
    after_gap = stream.update(payload(), metadata(6), "12345678", cards_valid=True)
    assert after_gap["would_send"] is False
    assert after_gap["confirmations"] == 1


def test_stale_frames_and_new_hand_reset_confirmation():
    stream = DecisionStream()
    stream.update(payload(), metadata(), "2861007497", cards_valid=True)
    stale = metadata(2)
    stale["captured_at"] = (datetime.now(UTC) - timedelta(seconds=10)).isoformat()
    assert stream.update(payload(), stale, "2861007497", cards_valid=True) is None
    assert not stream.update(payload(), metadata(3), "2861007498", cards_valid=True)["would_send"]


def test_new_hand_does_not_inherit_confirmed_raise_bounds():
    stream = DecisionStream()
    stream.update(payload(), metadata(1), "2862525208", cards_valid=True)
    assert stream.update(payload(), metadata(2), "2862525208", cards_valid=True)["would_send"]
    unknown = payload()
    unknown.update(min_raise_amount=None, max_raise_amount=None)
    for frame in (3, 4):
        result = stream.update(unknown, metadata(frame), "2862525253", cards_valid=True)
        assert not result["would_send"]
        assert result["request"]["min_raise_amount"] is None
        assert result["request"]["max_raise_amount"] is None
    assert result["confirmations"] == 2


def test_draft_artifacts_share_exact_frame_and_never_look_like_ready_request(tmp_path):
    recorder = Recorder(tmp_path)
    draft = DecisionStream().update(payload(), metadata(42), "2861007497", cards_valid=True)
    recorder.event(
        "decision_dry_run",
        {"frame_id": 42, **draft},
        "Пробный запрос заблокирован",
        frame=np.zeros((50, 100, 3), np.uint8),
    )
    recorder.close()
    assert not recorder.error
    base = recorder.path / "requests"
    assert (base / "00000042.png").exists()
    assert json.loads((base / "00000042.draft.json").read_text(encoding="utf8")) == payload()
    assert not list(base.glob("*.request.json"))
    evidence = json.loads((base / "00000042.evidence.json").read_text(encoding="utf8"))
    assert evidence["image"] == "requests/00000042.png"
    assert evidence["source"]["frame_id"] == 42


@pytest.mark.parametrize(
    "changes,error",
    [
        ({"min_raise_amount": 101}, "invalid_raise_bounds"),
        ({"can_check": True}, "check_with_call_amount"),
        ({"can_check": True}, "conflicting_check_call"),
        ({"call_amount_needed": 0}, "call_without_amount"),
        ({"can_bet": True}, "conflicting_bet_raise"),
        (
            {
                k: False
                for k in ("can_fold", "can_check", "can_call", "can_bet", "can_raise", "can_all_in")
            },
            "no_legal_actions",
        ),
    ],
)
def test_known_action_conflicts_are_reported_in_incomplete_draft(changes, error):
    data = payload()
    data["players"][0]["stack"] = None
    data.update(changes)
    errors = request_errors(data)
    assert "player_stack_unknown" in errors
    assert error in errors


def test_unknown_amounts_do_not_create_numeric_conflicts():
    data = payload()
    data.update(call_amount_needed=None, min_raise_amount=None, can_check=False)
    errors = request_errors(data)
    assert "call_without_amount" not in errors
    assert "invalid_raise_bounds" not in errors


def test_equal_capture_time_is_not_an_independent_confirmation():
    stream = DecisionStream()
    first = metadata(1)
    stream.update(payload(), first, "12345678", cards_valid=True)
    duplicate = {**first, "frame_id": 2}
    assert stream.update(payload(), duplicate, "12345678", cards_valid=True) is None
    assert stream.count == 1
    later = {
        **first,
        "frame_id": 3,
        "captured_at": (
            datetime.fromisoformat(first["captured_at"]) + timedelta(milliseconds=100)
        ).isoformat(),
    }
    result = stream.update(
        payload(),
        later,
        "12345678",
        cards_valid=True,
        now=datetime.fromisoformat(later["captured_at"]),
    )
    assert result["would_send"] is True


def test_capture_epoch_change_requires_new_confirmations():
    stream = DecisionStream()
    base = datetime.now(UTC)
    for frame, epoch in ((1, 1), (2, 1), (3, 2), (4, 2)):
        at = base + timedelta(milliseconds=100 * frame)
        source = {**metadata(frame), "captured_at": at.isoformat(), "evidence_epoch": epoch}
        result = stream.update(payload(), source, "12345678", cards_valid=True, now=at)
        assert result["would_send"] is (frame in (2, 4))
        assert result["confirmations"] == (2 if frame in (2, 4) else 1)


def test_emitted_draft_is_detached_from_mutable_live_inputs():
    stream = DecisionStream()
    request, source = payload(), metadata()
    draft = stream.update(request, source, "12345678", cards_valid=True)
    request["hero_hole_cards"][0] = "2c"
    request["players"][0]["stack"] = 0
    source["client_rect"][0] = 999
    assert draft["request"]["hero_hole_cards"] == ["Ah", "As"]
    assert draft["request"]["players"][0]["stack"] == 100
    assert draft["source"]["client_rect"][0] == 0
