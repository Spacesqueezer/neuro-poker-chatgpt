import json
from datetime import datetime
from pathlib import Path

import cv2
import pytest

from poker.hud.fast_table import analyze_fast_table
from poker.hud.live_evidence import LiveEvidence
from poker.hud.recognition import configure_ocr
from poker.hud.session_images import saved_frame_path


def test_fast_pipeline_confirms_two_saved_all_in_sources():
    root = Path("artifacts/hud/sessions/session_20261002_130712_79dc70")
    if not saved_frame_path(root, 1244).exists():
        pytest.skip("Local diagnostic frames unavailable")
    events = [
        json.loads(line)
        for p in root.glob("events.jsonl*")
        for line in p.read_text(encoding="utf8").splitlines()
    ]
    rows = {e["frame_id"]: e for e in events if e["kind"] == "frame"}
    configure_ocr()
    tracker = LiveEvidence()
    result = None
    for n in (1243, 1244):
        path = saved_frame_path(root, n)
        source = {**rows[n], "image": str(path), "evidence_epoch": tracker.epoch}
        context = analyze_fast_table(cv2.imread(str(path)))
        assert context["table_signals"]["slider_evidence"]["endpoint"] == "right"
        assert context["table_signals"]["controls"]["selected_wager"]["value"] == 155.55
        if n == 1244:
            field = context["table_signals"]["slider_evidence"]["field"]
            assert field["method"] == "geometric_caret_original_polarities_agree"
            assert field["original"]["text"] == "155,55|"
        result = tracker.update(context, source, now=datetime.fromisoformat(source["captured_at"]))
    confirmation = result["slider_endpoint"]
    assert confirmation["value"] == 155.55
    assert [s["frame_id"] for s in confirmation["confirmation_frames"]] == [1243, 1244]
    assert confirmation["legal_bound_confirmed"] is False
