import json

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("cv2")

from poker.hud.diagnostics import Recorder  # noqa: E402


def events(recorder):
    return [
        json.loads(line)
        for line in (recorder.path / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]


def test_advisor_sidecar_preserves_legacy_draft_and_evidence(tmp_path):
    recorder = Recorder(tmp_path)
    advisor = {
        "would_send": False,
        "model_called": False,
        "observation": {"schema_version": "advisor-observation/1"},
    }
    recorder.event(
        "decision_dry_run",
        {"frame_id": 7, "request": {"is_my_turn": True}, "would_send": False, "advisor": advisor},
        "Диагностический контракт",
    )
    recorder.close()
    base = recorder.path / "requests"
    assert json.loads((base / "00000007.advisor.json").read_text(encoding="utf8")) == advisor
    assert json.loads((base / "00000007.draft.json").read_text(encoding="utf8")) == {
        "is_my_turn": True
    }
    assert (
        json.loads((base / "00000007.evidence.json").read_text(encoding="utf8"))["advisor"]
        == advisor
    )
    assert not list(base.glob("*.request.json"))


def test_frame_event_and_human_notes_are_linked(tmp_path):
    recorder = Recorder(tmp_path)
    frame_id = recorder.frame(np.zeros((100, 200, 3), np.uint8), {"captured_at": "test"})
    recorder.event(
        "manual_name", {"frame_id": frame_id, "corrected_name": "Alice"}, "Исправлен ник на Alice"
    )
    recorder.close()
    rows = events(recorder)
    frame = next(r for r in rows if r["kind"] == "frame")
    assert (recorder.path / frame["image"]).exists()
    correction = next(r for r in rows if r["kind"] == "manual_name")
    assert correction["frame_id"] == frame["frame_id"]
    assert "Исправлен ник" in (recorder.path / "timeline.md").read_text(encoding="utf-8")
    assert rows[-1]["kind"] == "stop"
    assert not recorder.worker.is_alive()


def test_image_budget_preserves_text_without_deleting_old_data(tmp_path):
    marker = tmp_path / "existing.txt"
    marker.write_text("keep")
    recorder = Recorder(tmp_path, image_limit=1)
    recorder.frame(np.zeros((100, 200, 3), np.uint8), {})
    recorder.event("note", {"text": "Still recording"}, "Текст продолжается")
    recorder.close()
    assert recorder.limit_reached
    assert not list((recorder.path / "frames").iterdir())
    assert any(row["kind"] == "note" for row in events(recorder))
    assert marker.read_text() == "keep"


def test_text_ocr_frame_is_saved_losslessly_without_changing_jpeg_path(tmp_path):
    import cv2

    from poker.hud.session_images import saved_frame_path

    frame = np.random.default_rng(42).integers(0, 256, (80, 120, 3), dtype=np.uint8)
    recorder = Recorder(tmp_path)
    number = recorder.frame(frame, {}, lossless=True)
    recorder.close()
    event = next(r for r in events(recorder) if r["kind"] == "frame")
    assert event["image"].endswith(".jpg")
    path = recorder.path / event["lossless_image"]
    assert np.array_equal(cv2.imread(str(path)), frame)
    assert saved_frame_path(recorder.path, number) == path
    assert recorder.image_bytes == sum(
        p.stat().st_size for p in recorder.path.glob("*/*") if p.suffix in {".jpg", ".png"}
    )


def test_lossless_frames_share_the_image_budget(tmp_path):
    import cv2

    frame = np.random.default_rng(42).integers(0, 256, (80, 120, 3), dtype=np.uint8)
    jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])[1]
    png = cv2.imencode(".png", frame)[1]
    recorder = Recorder(tmp_path, image_limit=jpeg.nbytes + png.nbytes - 1)
    recorder.frame(frame, {}, lossless=True)
    recorder.close()
    event = next(r for r in events(recorder) if r["kind"] == "frame")
    assert (recorder.path / event["image"]).exists()
    assert event["lossless_image"] is None
    assert recorder.limit_reached
    assert not list((recorder.path / "ocr_frames").iterdir())


def test_replay_prefers_exact_same_frame_and_supports_old_sessions(tmp_path):
    from poker.hud.session_images import frame_candidates, saved_frame_path

    exact, request, jpeg = frame_candidates(tmp_path, 42)
    for path in (jpeg, request, exact):
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(b"image")
        assert saved_frame_path(tmp_path, 42) == path
    assert saved_frame_path(tmp_path, 43).name == "00000043.jpg"


def test_card_cache_does_not_reuse_changed_glyphs(monkeypatch):
    from poker.hud import cards

    cards.read_card_pixels.cache_clear()

    calls = []
    monkeypatch.setattr(cards, "read_rank", lambda image: (calls.append(1) or "A", 95))
    monkeypatch.setattr(cards, "read_suit", lambda image: ("s", 95))
    frame = np.zeros((100, 70, 3), np.uint8)
    cards.read_card_pixels(frame.shape, frame.tobytes())
    cards.read_card_pixels(frame.shape, frame.tobytes())
    frame[5, 5] = 255
    cards.read_card_pixels(frame.shape, frame.tobytes())
    assert len(calls) == 2
    cards.read_card_pixels.cache_clear()


def test_fast_pipeline_does_not_wait_for_name_ocr(monkeypatch):
    from poker.hud import pipeline

    def forbidden(_):
        raise AssertionError("Name OCR reached the fast card worker")

    monkeypatch.setattr(pipeline, "analyze", forbidden)
    result = pipeline.analyze_frame(np.zeros((600, 1000, 3), np.uint8), False)
    assert result.players == [] and not result.hand.valid
