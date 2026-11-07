# Optional HUD dependencies must be checked before importing the implementation.
# ruff: noqa: E402
import json
import sqlite3
from contextlib import closing

import pytest

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")
pytest.importorskip("pytesseract")

from poker.hud.models import PlayerObservation
from poker.hud.recognition import analyze, layout_panels
from poker.hud.storage import read_statistics, save_capture


def test_blank_frame_does_not_create_players():
    frame = np.zeros((600, 1000, 3), dtype=np.uint8)
    assert layout_panels(frame) == []
    assert analyze(frame) == []


def test_capture_preserves_raw_pixels_and_records_metadata(tmp_path):
    frame = np.full((120, 300, 3), 40, dtype=np.uint8)
    player = PlayerObservation((30, 40, 100, 40), "Alice", 90, "100", "recognized")
    output = save_capture(tmp_path, frame, [player], {"window": "Стол", "frame_id": 3})
    raw = cv2.imdecode(np.fromfile(output / "table.png", dtype=np.uint8), cv2.IMREAD_COLOR)
    assert np.array_equal(raw, frame)
    data = json.loads((output / "capture.json").read_text(encoding="utf-8"))
    assert data["frame_size"] == [300, 120]
    assert data["players"][0]["name"] == "Alice"
    assert data["frame_id"] == 3
    assert (output / "table_annotated.png").is_file()


def test_statistics_are_opt_in_and_missing_db_is_not_created(tmp_path):
    assert read_statistics(None, "Alice") is None
    database = tmp_path / "missing.db"
    with pytest.raises(sqlite3.OperationalError):
        read_statistics(database, "Alice")
    assert not database.exists()


def test_statistics_read_exact_identity_without_mutating_db(tmp_path):
    database = tmp_path / "players.db"
    with closing(sqlite3.connect(database)) as connection:
        connection.executescript("""
            CREATE TABLE players(id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE player_statistics(player_id INTEGER, hands INTEGER,
                vpip REAL, pfr REAL, aggression REAL);
            INSERT INTO players VALUES(1, 'Alice');
            INSERT INTO player_statistics VALUES(1, 100, .25, .15, 2.0);
        """)
        connection.commit()
    before = database.read_bytes()
    assert read_statistics(database, "Alice") == {
        "hands": 100,
        "vpip": 0.25,
        "pfr": 0.15,
        "aggression": 2.0,
    }
    assert read_statistics(database, "' OR 1=1 --") is None
    assert database.read_bytes() == before
