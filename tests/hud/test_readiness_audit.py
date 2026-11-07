import json
from datetime import UTC, datetime, timedelta

import pytest

from tools.audit_hud_readiness import blocker_group, read_events, render, summarize, turn_windows


def write_rows(path, rows):
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")


def test_rotated_logs_and_missing_advisor_never_count_as_ready(tmp_path):
    card = dict(
        kind="cards",
        at="2026-10-19T04:00:01+00:00",
        captured_at="2026-10-19T04:00:00+00:00",
        frame_id=1,
        hand=dict(my_turn=True, valid=True, odds={}),
    )
    draft = dict(card, kind="decision_dry_run")
    write_rows(tmp_path / "events.jsonl.1", [card])
    write_rows(tmp_path / "events.jsonl", [draft, dict(draft, advisor={"blockers": []})])
    report = summarize(tmp_path)
    assert len(report["input_sha256"]) == 2
    assert report["turn_cards"]["reported_valid"] == 1
    assert report["turn_cards"]["exact_images"] == 0
    assert report["turn_cards"]["accuracy_measured"] is False
    assert report["drafts"]["count"] == 2
    assert report["drafts"]["without_recorded_blockers"] == 0
    assert report["drafts"]["missing_advisor_diagnostics"] == 1
    assert report["latency_seconds"]["cards"]["p95"] == 1
    assert "без повторного OCR" in render([report])


def test_blocker_classification_keeps_unknown_reasons():
    assert blocker_group("stacks_unverified") == "producer_gates"
    assert blocker_group("history_incomplete") == "unimplemented_contract_fields"
    assert (
        blocker_group("player.4.hand_contribution_unknown_or_invalid")
        == "unimplemented_contract_fields"
    )
    assert blocker_group("player.4.stack_unknown_or_invalid") == "observation_or_other"
    assert blocker_group("new_future_reason") == "observation_or_other"


def test_corrupt_log_is_not_silently_skipped(tmp_path):
    (tmp_path / "events.jsonl").write_text('{"kind":', encoding="utf-8")
    with pytest.raises(ValueError, match="events.jsonl:1"):
        read_events(tmp_path)


def test_turn_window_does_not_credit_late_draft_or_another_epoch():
    base = datetime(2026, 10, 19, 4, tzinfo=UTC)

    def row(seconds, kind="cards", *, turn=True, epoch=1, result_seconds=None):
        return dict(
            kind=kind,
            frame_id=seconds,
            captured_at=(base + timedelta(seconds=seconds)).isoformat(),
            at=(base + timedelta(seconds=result_seconds or seconds)).isoformat(),
            evidence_epoch=epoch,
            hand=dict(my_turn=turn, hero=["As", "Kd"], board=[]),
            request=dict(hero_hole_cards=["As", "Kd"], board_cards=[]),
        )

    events = [row(1), row(3), row(4, turn=False), row(5), row(6, epoch=2)]
    events.extend(
        [
            row(1, "decision_dry_run", result_seconds=2),
            row(3, "decision_dry_run", result_seconds=5),
            row(5, "decision_dry_run", epoch=9),
        ]
    )
    windows = turn_windows(events)
    assert len(windows) == 3
    assert windows[0]["draft_frames"] == [1, 3]
    assert windows[0]["timely_draft_frames"] == [1]
    assert windows[1]["draft_frames"] == []
