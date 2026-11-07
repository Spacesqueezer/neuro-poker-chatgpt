import threading

import pytest

from poker.hud import context


def test_stack_workers_preserve_seats_and_isolate_failure(monkeypatch):
    gate = threading.Barrier(2, timeout=5)

    def read(frame, roi, *, read_status):
        assert not read_status
        if roi[0] < 2:
            gate.wait()
        if roi[0] == 1:
            raise RuntimeError("OCR failed")
        return {"value": roi[0] + 10, "roi": roi}

    monkeypatch.setattr(context, "read_stack", read)
    slots = [{"seat_index": 6 - i, "roi": [i, 0, 80, 30]} for i in range(7)]
    readings, errors = context.read_table_stacks(None, slots)
    assert list(readings) == list(range(6, -1, -1))
    assert readings[5] == {"value": None, "error": "OCR failed"}
    assert errors == ["stack_5: OCR failed"]
    assert [readings[s]["value"] for s in (6, 4, 3, 2, 1, 0)] == [10, 12, 13, 14, 15, 16]


def test_empty_table_does_not_start_stack_ocr(monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("No OCR without seats")

    monkeypatch.setattr(context, "read_stack", unexpected)
    assert context.read_table_stacks(None, []) == ({}, [])


@pytest.mark.parametrize(
    "change", [None, "weak", "foreign_roi", "no_words", "unknown_action", "settlement"]
)
def test_only_confident_local_action_suppresses_stack_ocr(monkeypatch, change):
    label = {
        "action": "call",
        "roi": [3, 12, 94, 25],
        "words": [{"text": "УРАВНЯТЬ", "confidence": 92}],
    }
    slot = {"seat_index": 2, "roi": [0, 0, 100, 60], "action_label": label}
    if change == "weak":
        label["words"][0]["confidence"] = 84
    elif change == "foreign_roi":
        label["roi"][0] = 103
    elif change == "no_words":
        label["words"] = []
    elif change == "unknown_action":
        label["action"] = "other"
    elif change == "settlement":
        slot["settlement_label"] = {"text": "won"}
    calls = []

    def read(*args, **kwargs):
        calls.append(True)
        return {"value": 25}

    monkeypatch.setattr(context, "read_stack", read)
    readings, errors = context.read_table_stacks(None, [slot])
    assert not errors
    if change is None:
        assert not calls
        assert readings[2]["value"] is None
        assert readings[2]["rejection"] == "stack_hidden_by_action_caption"
        label["words"].clear()
        assert readings[2]["action_evidence"]["words"]
    else:
        assert calls == [True]
        assert readings[2]["value"] == 25
