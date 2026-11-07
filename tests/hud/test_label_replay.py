import json
from copy import deepcopy

import pytest

from tools.replay_hud_hands import cached_rows, replay_observation


def prepare(tmp_path, image=None):
    session = tmp_path / "session"
    session.mkdir()
    events = [
        {"kind": "frame", "frame_id": 1, "at": "03"},
        {"kind": "pause", "at": "04"},
        {"kind": "frame", "frame_id": 2, "at": "05"},
    ]
    (session / "events.jsonl").write_text("\n".join(map(json.dumps, events)))
    cache = tmp_path / "observations.jsonl"
    cache.write_text(
        "\n".join(json.dumps({"frame_id": i, "captured_at": "01", "image": image}) for i in (1, 2))
    )
    return session, cache


def test_refresh_keeps_event_order_and_pause_even_with_delayed_frames(tmp_path):
    session, cache = prepare(tmp_path)
    result = cached_rows(session, cache)
    assert [r["kind"] for r in result] == ["frame", "pause", "frame"]
    assert [r["at"] for r in result] == ["03", "04", "05"]
    assert result[0]["captured_at"] == "01"
    assert result[0]["players"] == []


def test_refresh_rejects_another_sessions_images(tmp_path):
    session, cache = prepare(tmp_path, str(tmp_path / "other" / "00000001.jpg"))
    with pytest.raises(ValueError, match="different session"):
        cached_rows(session, cache)


def test_refresh_rejects_unknown_frame(tmp_path):
    session, cache = prepare(tmp_path)
    with cache.open("a") as stream:
        stream.write('\n{"frame_id": 3, "captured_at": "06"}')
    with pytest.raises(ValueError, match="missing"):
        cached_rows(session, cache)


@pytest.mark.parametrize(
    "key,value",
    [
        ("captured_at", "different capture"),
        ("window", 1234),
        ("client_rect", [0, 0, 1200, 900]),
    ],
)
def test_refresh_rejects_metadata_mismatched_to_original_capture(tmp_path, key, value):
    session, cache = prepare(tmp_path)
    path = session / "events.jsonl"
    events = [json.loads(line) for line in path.read_text().splitlines()]
    events[0][key] = value
    path.write_text("\n".join(map(json.dumps, events)))
    with pytest.raises(ValueError, match=f"Cached {key} differs"):
        cached_rows(session, cache)


def test_refresh_normalizes_legacy_null_players(tmp_path):
    session, cache = prepare(tmp_path)
    rows = [json.loads(line) for line in cache.read_text().splitlines()]
    rows[0]["players"] = None
    cache.write_text("\n".join(map(json.dumps, rows)))
    assert cached_rows(session, cache)[0]["players"] == []


def test_refresh_preserves_numeric_context_epoch_and_independent_saved_snapshot():
    row = {
        "frame_id": 1,
        "captured_at": "2026-01-01T00:00:01+00:00",
        "window": "table",
        "client_rect": (0, 0, 100, 100),
        "evidence_epoch": 7,
        "players": None,
    }
    context = {
        "hand_id": {"value": "12345678", "confidence": 95},
        "decision_hand": {"hero": ("Ah", "Kd"), "board": ()},
        "stack_readings": {"0": {"value": 100, "confidence": 95}},
        "table_signals": {"slots": []},
    }
    before = deepcopy(context)
    signals = {"slots": [{"seat_index": 0, "current_bet": 2}], "pot": {"value": 3}}
    result = replay_observation(row, context, signals, "frame.png")
    assert result["evidence_epoch"] == 7
    assert result["players"] == []
    assert result["context"]["stack_readings"] == context["stack_readings"]
    assert result["context"]["table_signals"] == signals
    assert result["context"]["decision_hand"]["board"] == []
    assert context == before
    assert result == json.loads(json.dumps(result))
    context["stack_readings"]["0"]["value"] = 50
    signals["pot"]["value"] = 999
    assert result["context"]["stack_readings"]["0"]["value"] == 100
    assert result["context"]["table_signals"]["pot"]["value"] == 3
