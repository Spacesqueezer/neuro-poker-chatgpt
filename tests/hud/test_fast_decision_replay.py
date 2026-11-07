import json
from copy import deepcopy
from datetime import timedelta

import numpy as np
import pytest

from poker.hud.decision_observer import fast_decision_draft
from poker.hud.decision_stream import DecisionStream
from poker.hud.live_evidence import LiveEvidence
from tests.hud.test_decision_observer import observation
from tools import replay_hud_fast_decisions as replay
from tools.audit_advisor_contract import rebuild_hud


def test_contract_audit_keeps_late_name_history_out_of_fast_requests():
    live, stream, events = LiveEvidence(), DecisionStream(), []
    for n in (1, 2, 3):
        source, context, _ = observation(n)
        facts = live.update(context, source, now=replay.dt(source["captured_at"]))
        events.append({**source, "kind": "fast_table", "context": context, "accepted": True})
        if n == 2:
            other = deepcopy(events[-1])
            other["kind"] = "names"
            other["context"]["hand_id"]["value"] = "99999999"
            other["captured_at"] = (
                replay.dt(source["captured_at"]) + timedelta(milliseconds=100)
            ).isoformat()
            events.append(other)
    draft = fast_decision_draft(
        context, source, facts, live.tracker, stream, now=replay.dt(source["captured_at"])
    )
    events.append({**draft, "kind": "decision_dry_run"})
    rebuilt = list(rebuild_hud(events))
    assert len(rebuilt) == 1
    diagnostic = rebuilt[0][1]
    assert "hand_fragment_source_mismatch" not in diagnostic["blockers"]
    assert diagnostic["observation"]["evidence"]["hand_fragment"]["hand_id"] == "12345678"


@pytest.mark.parametrize("interruption", ["fast_table", "fast_table_error", "window"])
def test_contract_audit_resets_rejected_fragment_like_live_collector(interruption):
    live, stream, events = LiveEvidence(), DecisionStream(), []
    source, context, _ = observation(1)
    live.update(context, source, now=replay.dt(source["captured_at"]))
    events.append({**source, "kind": "fast_table", "context": context, "accepted": True})
    source, context, _ = observation(2)
    events.append({**source, "kind": interruption, "context": context, "accepted": False})
    live.reset()
    live.epoch = source["evidence_epoch"]
    source, context, _ = observation(3)
    facts = live.update(context, source, now=replay.dt(source["captured_at"]))
    events.append({**source, "kind": "fast_table", "context": context, "accepted": True})
    draft = fast_decision_draft(
        context, source, facts, live.tracker, stream, now=replay.dt(source["captured_at"])
    )
    events.append({**draft, "kind": "decision_dry_run"})
    [(event, rebuilt)] = list(rebuild_hud(events))
    assert {k: v for k, v in rebuilt.items() if k != "build_ms"} == {
        k: v for k, v in event["advisor"].items() if k != "build_ms"
    }


def test_replay_skips_busy_captures_and_cancels_finished_turn(tmp_path, monkeypatch):
    session = tmp_path / "session"
    images = session / "ocr_frames"
    images.mkdir(parents=True)
    events = []
    for n in (1, 2, 3):
        source, context, _ = observation(n)
        (images / f"{n:08d}.png").write_bytes(b"same frame")
        events.append(
            {**source, "at": source["captured_at"], "kind": "fast_table", "context": context}
        )
        hand = deepcopy(context["decision_hand"])
        hand["my_turn"] = n != 2
        events.append({**source, "at": source["captured_at"], "kind": "cards", "hand": hand})
    (session / "events.jsonl").write_text(
        "\n".join(json.dumps(e) for e in events), encoding="utf-8"
    )
    ticks = iter([0.0, 1.5, 1.5, 10.0, 10.1, 10.1])
    monkeypatch.setattr(replay, "perf_counter", lambda: next(ticks))
    monkeypatch.setattr(replay, "configure_ocr", lambda: None)
    monkeypatch.setattr(replay.cv2, "imread", lambda _: np.zeros((20, 20, 3), np.uint8))
    monkeypatch.setattr(replay, "analyze_fast_table", lambda *a: observation()[1])
    output = tmp_path / "result"
    summary = replay.replay(session, output)
    assert summary["counts"] == {"processed": 2, "skipped_worker_busy": 1}
    drafts = [
        json.loads(line)
        for line in (output / "drafts.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [r["frame_id"] for r in drafts] == [3]
    assert summary["without_blockers"] == 0
    assert summary["model_called"] is False
