import threading

import pytest

from poker.hud import recognition


def test_parallel_name_reads_keep_physical_order_and_skip_absent_panels(monkeypatch):
    candidates = [(i, 0, 100, 60) for i in range(7)]
    barrier = threading.Barrier(2, timeout=5)
    monkeypatch.setattr(recognition, "find_panels", lambda frame: [])
    monkeypatch.setattr(recognition, "layout_panels", lambda frame: candidates)

    def panel(frame, roi, detected):
        assert not detected
        if roi[0] < 2:
            barrier.wait()
        return roi[0] if roi[0] != 3 else None

    monkeypatch.setattr(recognition, "analyze_panel", panel)
    assert recognition.analyze(None) == [0, 1, 2, 4, 5, 6]


def test_worker_failure_is_not_silently_reported_as_an_empty_table(monkeypatch):
    monkeypatch.setattr(recognition, "find_panels", lambda frame: [(0, 0, 100, 60)])
    monkeypatch.setattr(recognition, "layout_panels", lambda frame: [])

    def broken(*args):
        raise RuntimeError("OCR timeout")

    monkeypatch.setattr(recognition, "analyze_panel", broken)
    with pytest.raises(RuntimeError, match="OCR timeout"):
        recognition.analyze(None)
