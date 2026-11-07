"""Resolve only same-session, same-frame images, preferring lossless evidence."""

from pathlib import Path


def frame_candidates(session, frame_id):
    root = Path(session)
    stem = f"{frame_id:08d}"
    return (
        root / "ocr_frames" / f"{stem}.png",
        root / "requests" / f"{stem}.png",
        root / "frames" / f"{stem}.jpg",
    )


def saved_frame_path(session, frame_id):
    candidates = frame_candidates(session, frame_id)
    return next((p for p in candidates if p.is_file()), candidates[-1])
