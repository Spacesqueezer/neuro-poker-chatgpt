import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from tools.audit_hud_contributions import render_report, scope_replay_result, select_hand_events


def event(kind, second, **extra):
    return dict(kind=kind, captured_at=f"2026-10-05T12:00:{second:02d}", **extra)


def test_replay_selects_padding_and_capture_boundaries_without_changing_events():
    rows = [
        event("frame", 7),
        event("frame", 8),
        event("names", 10, context={"hand_id": {"value": "12345678", "confidence": 90}}),
        event("frame", 11),
        {"kind": "pause", "at": "2026-10-05T12:00:09"},
        event("frame", 12),
        event("frame", 13),
    ]
    original = deepcopy(rows)
    selected = select_hand_events(rows, "12345678", padding_seconds=2)
    assert selected == [rows[1], rows[4], rows[3], rows[5]]
    assert rows == original


def test_default_padding_covers_early_blinds_before_slow_text_sample():
    rows = [
        event("frame", 4),
        event("frame", 6),
        event("frame", 16),
        event("names", 10, context={"hand_id": {"value": "12345678", "confidence": 95}}),
    ]
    assert select_hand_events(rows, "12345678") == [rows[1]]
    assert select_hand_events(rows, "12345678", 2) == []


@pytest.mark.parametrize("padding", [-1, 31, float("nan"), float("inf")])
def test_bad_replay_padding_is_rejected(padding):
    with pytest.raises(ValueError, match="Replay padding"):
        select_hand_events([], "12345678", padding)


def test_replay_rejects_unobserved_or_uncertain_hand():
    rows = [event("names", 10, context={"hand_id": {"value": "12345678", "confidence": 79}})]
    with pytest.raises(ValueError, match="No confident observations"):
        select_hand_events(rows, "12345678")


def test_report_does_not_present_repeated_pot_as_final_payment():
    text = render_report(dict(session="test", intervals=[], pot_movements=[]))
    assert "не окончательные суммы" in text
    assert "Причина остаётся неизвестной" in text


def test_single_hand_report_excludes_neighbor_finances_but_preserves_source_result():
    keys = ("points", "intervals", "pot_movements", "action_stack_intervals", "return_candidates")
    result = {
        key: [dict(hand_id="12345678", value=2), dict(hand_id="87654321", value=100)]
        for key in keys
    }
    original = deepcopy(result)
    scoped = scope_replay_result(result, "12345678")
    assert result == original
    assert all(scoped[key] == [result[key][0]] for key in keys)
    assert scoped["excluded_neighbor_results"] == dict.fromkeys(keys, 1)


def test_single_hand_report_with_no_financial_evidence_stays_empty():
    result = scope_replay_result({"points": [{"hand_id": "87654321"}]}, "12345678")
    assert result["points"] == []
    assert result["return_candidates"] == []


def test_fresh_replay_and_saved_json_have_identical_card_container_types(tmp_path, monkeypatch):
    import cv2

    from poker.hud import cards, client_id, hand, recognition, table_signals
    from tools import audit_hud_contributions as tool

    image = tmp_path / "frame.png"
    image.write_bytes(b"test image placeholder")
    monkeypatch.setattr(tool, "saved_frame_path", lambda *_: image)
    monkeypatch.setattr(cv2, "imread", lambda *_: object())
    monkeypatch.setattr(recognition, "configure_ocr", lambda: None)
    monkeypatch.setattr(recognition, "layout_panels", lambda _: [])
    monkeypatch.setattr(cards, "find_cards", lambda _: [])
    monkeypatch.setattr(
        hand,
        "observe",
        lambda _: SimpleNamespace(
            to_dict=lambda: {"hero": ("Ah", "Kd"), "board": (), "valid": True}
        ),
    )
    monkeypatch.setattr(
        client_id, "read_hand_id", lambda _: {"value": "12345678", "confidence": 95}
    )
    monkeypatch.setattr(table_signals, "anchored_pot", lambda _: {"value": 3})
    source = event("frame", 10, frame_id=1, window="table", client_rect=[0, 0, 100, 100])
    result = tool.replay_hand(tmp_path, [], [source], tmp_path)
    saved = [
        json.loads(line)
        for line in (tmp_path / "observations.jsonl").read_text(encoding="utf8").splitlines()
    ]
    assert result == saved
    assert result[0]["context"]["decision_hand"]["board"] == []
    assert result[0]["context"]["decision_hand"]["hero"] == ["Ah", "Kd"]
