from concurrent.futures import Future

import numpy as np
import pytest

from poker.hud import fast_table
from tests.hud.test_live_evidence_app import app


@pytest.mark.parametrize("invalid", ["paused", "epoch", "window", "generation"])
def test_fast_worker_rejects_old_capture_without_database_or_request(tmp_path, invalid):
    hud = app(tmp_path)
    source, generation, _, frame = hud.names_context
    context = hud.names_future.result()[1]
    hud.fast_context = source, generation, frame
    hud.fast_future = Future()
    hud.fast_future.set_result(context)
    if invalid == "paused":
        hud.paused = True
    elif invalid == "epoch":
        hud.reset_capture_evidence()
    elif invalid == "generation":
        hud.generation += 1
    else:
        hud.desktop.rect.return_value = (10, 0, 1200, 1000)
    hud.collect_fast_table()
    event = hud.recorder.event.call_args
    assert event.args[0] == "fast_table"
    assert event.args[1]["accepted"] is False
    assert hud.fast_future is None
    assert hud.fast_evidence.previous is None
    hud.stats_collector.observe.assert_not_called()


def test_fast_worker_records_same_frame_context(tmp_path):
    hud = app(tmp_path)
    source, generation, _, frame = hud.names_context
    hud.fast_context = source, generation, frame
    hud.fast_future = Future()
    hud.fast_future.set_result(hud.names_future.result()[1])
    hud.collect_fast_table()
    calls = {c.args[0]: c for c in hud.recorder.event.call_args_list}
    event = calls["fast_table"].args[1]
    assert event["accepted"] is True
    assert event["frame_id"] == source["frame_id"]
    assert event["evidence"]["model_called"] is False
    draft = calls["decision_dry_run"].args[1]
    assert draft["decision_source"] == "fast_table"
    assert draft["would_send"] is False and draft["model_called"] is False
    assert all(p["name"] == "" for p in draft["request"]["players"])
    assert np.array_equal(calls["decision_dry_run"].kwargs["frame"], frame)
    hud.stats_collector.observe.assert_not_called()


def test_fast_reader_rejects_incomplete_layout_without_ocr(monkeypatch):
    monkeypatch.setattr(fast_table, "layout_panels", lambda f: [])
    result = fast_table.analyze_fast_table(np.zeros((100, 100, 3), np.uint8))
    assert result["errors"] == ["layout_unknown"]
