from pathlib import Path

import pytest

from poker.hud.models import PlayerObservation
from poker.hud.player_store import LiveCollector, PlayerStore, describe_style
from poker.hud.state import Seat, TableState


@pytest.fixture
def store(tmp_path):
    db = PlayerStore(tmp_path / "players.sqlite3")
    yield db
    db.close()


def table(name="Alice", score=95, manual=False):
    state = TableState()
    state.size = (1000, 600)
    state.seats[1] = Seat(
        1,
        PlayerObservation((100, 100, 120, 50), name, score, "100", "recognized"),
        name=name,
        confirmations=2,
        manual=manual,
    )
    return state


def test_explicit_alias_merge_survives_restart_and_keeps_unique_hands(store):
    for name, source, numbers in [
        ("ghOst_", "old", ["2860834901", "2860834902"]),
        ("gh0st_", "new", ["2860834902", "2860834903"]),
    ]:
        collector = LiveCollector(store, source)
        for i, number in enumerate(numbers):
            observe(collector, table(name), i * 2, number=number)
            observe(collector, table(name), i * 2 + 1, number=number)
        store.set_note(name, source)
    store.correct_identity("ghOst_", "gh0st_", {"source": "manual"})
    assert store.summary("ghOst_")["hands"] == 3
    assert store.summary("gh0st_")["hands"] == 3
    assert set(store.summary("gh0st_")["note"].splitlines()) == {"old", "new"}
    assert store.connection.execute("SELECT COUNT(*) FROM hud_players").fetchone()[0] == 1
    reopened = PlayerStore(store.path)
    try:
        assert reopened.resolve_name("ghOst_") == ("gh0st_", True)
        assert reopened.resolve_name("otherO") == ("otherO", False)
        collector = LiveCollector(reopened, "restart")
        observe(collector, table("ghOst_"), 1)
        observe(collector, table("ghOst_"), 2)
        assert reopened.summary("gh0st_")["hands"] == 3
        assert reopened.connection.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        reopened.close()


def context(number="2860834901", hero=True, confidence=95):
    return {"hand_id": {"value": number, "confidence": confidence}, "hero_visible": hero}


def observe(collector, state, frame, **options):
    collector.observe(context(**options), state, {"frame_id": frame, "window": "Стол #3561"})


def test_two_distinct_frames_and_unique_hands_survive_restart(store):
    collector = LiveCollector(store, "session1")
    state = table()
    observe(collector, state, 1)
    observe(collector, state, 1)
    assert store.summary("Alice")["hands"] == 0
    observe(collector, state, 2)
    assert store.summary("Alice")["hands"] == 1
    restarted = LiveCollector(store, "session2")
    observe(restarted, state, 1)
    observe(restarted, state, 2)
    assert store.summary("alice")["hands"] == 1
    observe(restarted, state, 3, number="2860836114")
    observe(restarted, state, 4, number="2860836114")
    assert store.summary("Alice")["hands"] == 2


def test_uncertain_identity_is_not_credited_until_manual_correction(store):
    collector = LiveCollector(store, "session")
    state = table(score=60)
    observe(collector, state, 1)
    observe(collector, state, 2)
    assert store.summary("Alice")["hands"] == 0
    state.correct(1, "Correct_Name")
    collector.correct_current(state)
    assert store.summary("Correct_Name")["hands"] == 1
    assert store.summary("Alice")["hands"] == 0


def test_hidden_name_keeps_credit_but_conflict_revokes_current_attribution(store):
    collector = LiveCollector(store, "session")
    state = table()
    observe(collector, state, 1)
    observe(collector, state, 2)
    state.seats[1].observation.confidence = 0
    state.seats[1].observation.name = ""
    observe(collector, state, 3)
    assert store.summary("Alice")["hands"] == 1
    state.seats[1].conflict = True
    observe(collector, state, 4)
    assert store.summary("Alice")["hands"] == 0
    state.correct(1, "Bob")
    collector.correct_current(state)
    assert store.summary("Bob")["hands"] == 1


def test_spectating_or_unknown_hand_never_counts(store):
    collector = LiveCollector(store, "session")
    state = table()
    observe(collector, state, 1, hero=False)
    observe(collector, state, 2, hero=False)
    observe(collector, state, 3, confidence=40)
    assert store.summary("Alice")["hands"] == 0
    observe(collector, state, 4)
    observe(collector, state, 5)
    assert store.summary("Alice")["hands"] == 1


def test_duplicate_names_and_hero_are_excluded(store):
    state = table()
    state.seats[2] = Seat(
        2,
        PlayerObservation((800, 100, 120, 50), "Alice", 95, "100", "recognized"),
        name="Alice",
        confirmations=2,
    )
    state.seats[3] = Seat(
        3,
        PlayerObservation((450, 500, 120, 50), "Hero", 95, "100", "recognized"),
        name="Hero",
        confirmations=2,
    )
    collector = LiveCollector(store, "session")
    observe(collector, state, 1)
    observe(collector, state, 2)
    assert store.summary("Alice")["hands"] == 0
    assert store.summary("Hero")["hands"] == 0


@pytest.mark.parametrize("hero", range(7))
def test_statistics_excludes_selected_physical_hero_not_tracker_key(store, hero):
    rois = [
        (200, 100, 120, 50),
        (680, 100, 120, 50),
        (0, 280, 120, 50),
        (880, 280, 120, 50),
        (100, 450, 120, 50),
        (780, 450, 120, 50),
        (450, 500, 120, 50),
    ]
    state = TableState()
    state.size = (1000, 600)
    for i, roi in enumerate(rois):
        key, name = 20 + i, f"Player{i}"
        state.seats[key] = Seat(
            key,
            PlayerObservation(roi, name, 95, "100", "recognized"),
            name=name,
            confirmations=2,
        )
    observation = {
        **context(),
        "hero_seat": hero,
        "table_signals": {
            "slots": [{"seat_index": i, "roi": list(roi)} for i, roi in enumerate(rois)]
        },
    }
    collector = LiveCollector(store, "selected_hero")
    for frame in (1, 2):
        collector.observe(
            observation,
            state,
            {
                "frame_id": frame,
                "window": "Стол #3561",
                "hero_seat": hero,
            },
        )
    for i in range(7):
        assert store.summary(f"Player{i}")["hands"] == (0 if i == hero else 1)


def test_statistics_waits_for_layout_at_noncentral_hero(store):
    collector = LiveCollector(store, "unknown_layout")
    for frame in (1, 2):
        collector.observe(
            {**context(), "hero_seat": 4},
            table(),
            {
                "frame_id": frame,
                "window": "Стол #3561",
                "hero_seat": 4,
            },
        )
    assert store.summary("Alice")["hands"] == 0
    assert collector.current is None
    assert "место героя" in collector.status


def test_backup_is_portable_and_notes_persist(store, tmp_path):
    collector = LiveCollector(store, "session")
    observe(collector, table(), 1)
    observe(collector, table(), 2)
    store.set_note("Alice", "Часто повышает; проверить на большей выборке")
    destination = store.backup(tmp_path / "copy.sqlite3")
    restored = PlayerStore(destination)
    try:
        assert restored.summary("Alice") == store.summary("Alice")
        assert restored.summary("Alice")["hands"] == 1
        assert "неизвестен" in restored.summary("Alice")["style"]
    finally:
        restored.close()
    with pytest.raises(ValueError):
        store.backup(destination)


def test_actions_are_deduplicated_and_raw_ocr_is_not_a_verified_source(store):
    key = store.save(
        "2860834901", "3561", "test", list(table().seats.values()), (1000, 600), True, True, {}
    )
    for _ in range(2):
        store.record_action("event1", key, "Alice", "raise", "manual", {"checked": True})
    assert store.connection.execute("SELECT COUNT(*) FROM hud_actions").fetchone()[0] == 1
    with pytest.raises(ValueError):
        store.record_action("event2", key, "Alice", "raise", "raw_ocr", {"text": "raise"})
    assert "неизвестен" in describe_style({"raise": 100}, 1)
    assert "часто ставит" in describe_style({"raise": 20, "call": 5}, 5)


def test_client_hand_id_on_local_capture():
    cv2 = pytest.importorskip("cv2")
    from poker.hud.client_id import read_hand_id
    from poker.hud.recognition import configure_ocr

    path = (
        Path(__file__).resolve().parents[2] / "captures/hud_20260909_225454_223431_66f9de/table.png"
    )
    if not path.exists():
        pytest.skip("Local capture not present")
    configure_ocr()
    result = read_hand_id(cv2.imread(str(path)))
    assert result["value"] == "2860834901" and result["confidence"] >= 80


def test_upgrade_preserves_simulation_players_without_counting_them(tmp_path):
    import sqlite3
    from contextlib import closing

    from poker.statistics.database.migrations import MigrationConfig, upgrade_database

    path = tmp_path / "legacy.sqlite3"
    config = MigrationConfig(
        "sqlite:///" + path.as_posix(), str(Path(__file__).resolve().parents[2] / "alembic.ini")
    )
    upgrade_database(config, "0005_street_tracker_metrics")
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("INSERT INTO players(id,name) VALUES(1,'Simulation_Alice')")
        connection.commit()
    database = PlayerStore(path)
    try:
        assert (
            database.connection.execute("SELECT name FROM players WHERE id=1").fetchone()[0]
            == "Simulation_Alice"
        )
        assert database.summary("Simulation_Alice")["hands"] == 0
    finally:
        database.close()


def test_action_cannot_be_assigned_to_unrelated_player_or_reuse_event_id(store):
    key = store.save(
        "2860834901", "3561", "test", list(table().seats.values()), (1000, 600), True, True, {}
    )
    store.set_note("Bob", "Знакомый игрок")
    with pytest.raises(ValueError):
        store.record_action("event", key, "Bob", "raise", "manual", {"checked": True})
    store.record_action("event", key, "Alice", "raise", "manual", {"checked": True})
    with pytest.raises(ValueError):
        store.record_action("event", key, "Alice", "fold", "manual", {"checked": True})
