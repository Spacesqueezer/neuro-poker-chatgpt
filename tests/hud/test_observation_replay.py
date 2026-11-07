import json
import sys

from tools import replay_hud_observations as replay
from tools.audit_hud_requests import matched_controls


def test_replay_uses_exact_saved_name_frames_and_keeps_reading_errors(tmp_path, monkeypatch):
    session = tmp_path / "session"
    (session / "frames").mkdir(parents=True)
    (session / "frames" / "00000001.jpg").write_bytes(b"fake image")
    meta = {
        "frame_id": 1,
        "captured_at": "2026-09-14T09:00:00+00:00",
        "window": 12,
        "client_rect": [10, 20, 100, 80],
    }
    events = [
        {**meta, "kind": "frame"},
        {**meta, "kind": "names", "players": [{"name": "old OCR"}]},
        {**meta, "kind": "names", "frame_id": 2},
    ]
    (session / "events.jsonl").write_text("\n".join(map(json.dumps, events)))
    context = {
        "errors": ["table_signals: failed"],
        "decision_hand": {"valid": False},
        "table_signals": {},
    }
    calls = []
    monkeypatch.setattr(replay, "configure_ocr", lambda: None)
    monkeypatch.setattr(replay.cv2, "imread", lambda path: calls.append(path) or "pixels")
    monkeypatch.setattr(replay, "analyze_names", lambda image: ([], context))
    output = tmp_path / "output"
    monkeypatch.setattr(sys, "argv", ["replay", str(session), "--output", str(output)])
    replay.main()
    folder = next(output.iterdir())
    row = json.loads((folder / "observations.jsonl").read_text())
    control = json.loads((folder / "controls.jsonl").read_text())
    summary = json.loads((folder / "summary.json").read_text())
    assert len(calls) == 1
    assert row["players"] == []
    assert row["context"]["errors"] == context["errors"]
    assert matched_controls(row, control)
    assert control["controls"] == {}
    assert summary["missing_images"] == 1
    assert summary["error_frames"] == 1
    assert summary["model_called"] is False
