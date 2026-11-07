"""Readable rotating logs, reproducible captures, optional read-only statistics."""

import json
import logging
import sqlite3
import uuid
from contextlib import closing
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

import cv2

from poker.hud.recognition import annotate


def create_log(directory):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"hud_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}.log"
    logger = logging.getLogger(str(path))
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handler = RotatingFileHandler(path, maxBytes=5_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger, path


def save_capture(root, frame, observations, metadata):
    directory = root / f"hud_{datetime.now():%Y%m%d_%H%M%S_%f}_{uuid.uuid4().hex[:6]}"
    directory.mkdir(parents=True)
    for name, image in [
        ("table.png", frame),
        (
            "table_annotated.png",
            annotate(frame, observations, metadata.get("hand", {}).get("cards", [])),
        ),
    ]:
        ok, encoded = cv2.imencode(".png", image)
        if not ok:
            raise OSError(f"Cannot encode {name}")
        encoded.tofile(directory / name)
    payload = {
        "schema_version": 2,
        "saved_at": datetime.now(UTC).isoformat(),
        "frame_size": [frame.shape[1], frame.shape[0]],
        "players": [p.to_dict() for p in observations],
        **metadata,
    }
    (directory / "capture.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return directory


def read_statistics(database: Path | None, name: str):
    """Only an explicitly selected DB is used; simulation stats are not live stats."""
    if not database or not name:
        return None
    with closing(
        sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True, timeout=1)
    ) as connection:
        row = connection.execute(
            "SELECT s.hands,s.vpip,s.pfr,s.aggression FROM players p "
            "JOIN player_statistics s ON s.player_id=p.id WHERE p.name=?",
            (name,),
        ).fetchone()
    return dict(zip(("hands", "vpip", "pfr", "aggression"), row, strict=True)) if row else None
