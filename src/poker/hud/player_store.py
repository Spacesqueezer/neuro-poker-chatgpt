"""Portable live-player ledger. Counts are derived from unique observed hands."""

import json
import math
import re
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config

from poker.hud.player_profile import describe_style


def player_key(name, room="pokerdom"):
    name = name.strip()
    if not name or len(name) > 128:
        raise ValueError("Пустое или слишком длинное имя")
    return room + ":" + name.casefold()


def hero_source(context, metadata):
    """Resolve the selected physical plaque, independently of nickname tracker keys."""
    hero = context.get("hero_seat", metadata.get("hero_seat", 6))
    if type(hero) is not int or not 0 <= hero <= 6 or metadata.get("hero_seat", hero) != hero:
        return None
    slots = context.get("table_signals", {}).get("slots", [])
    roi = None
    if slots:
        if sorted(s.get("seat_index", -1) for s in slots) != list(range(7)):
            return None
        roi = next(s.get("roi") for s in slots if s["seat_index"] == hero)
        if (
            not isinstance(roi, (list, tuple))
            or len(roi) != 4
            or not all(type(v) in (int, float) and math.isfinite(v) for v in roi)
            or min(roi[:2]) < 0
            or min(roi[2:]) <= 0
        ):
            return None
    elif hero != 6:
        return None  # The old central geometry cannot identify a moved hero.
    return {**metadata, "hero_seat": hero, "hero_roi": list(roi) if roi else None}


class PlayerStore:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        config = Config()
        config.set_main_option(
            "script_location", str(Path(__file__).resolve().parents[3] / "migrations")
        )
        config.attributes["database_url"] = "sqlite:///" + self.path.as_posix()
        command.upgrade(config, "head")
        self.connection = sqlite3.connect(self.path, timeout=0.25)
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.row_factory = sqlite3.Row
        self.revision = 0

    def resolve_name(self, name):
        if not name:
            return name, False
        row = self.connection.execute(
            "SELECT p.display_name FROM hud_aliases a JOIN hud_players p "
            "ON p.player_key=a.player_key WHERE a.alias_key=?",
            (player_key(name),),
        ).fetchone()
        return (row[0], True) if row else (name, False)

    def correct_identity(self, old_name, new_name, evidence):
        """Explicit alias only: move history without summing duplicate hands."""
        old_key = player_key(self.resolve_name(old_name)[0])
        new_name = self.resolve_name(new_name)[0].strip()
        new_key = player_key(new_name)
        now = datetime.now(UTC).isoformat()
        with self.connection as db:
            db.execute(
                "INSERT OR IGNORE INTO hud_players VALUES (?,?,?,'',?,?)",
                (new_key, "pokerdom", new_name, now, now),
            )
            if old_key != new_key:
                old = db.execute(
                    "SELECT * FROM hud_players WHERE player_key=?", (old_key,)
                ).fetchone()
                if old:
                    target = db.execute(
                        "SELECT note FROM hud_players WHERE player_key=?", (new_key,)
                    ).fetchone()[0]
                    note = "\n".join(dict.fromkeys(n for n in (target, old["note"]) if n))
                    db.execute(
                        "UPDATE hud_players SET note=?, first_seen=MIN(first_seen,?), "
                        "last_seen=MAX(last_seen,?) WHERE player_key=?",
                        (note, old["first_seen"], old["last_seen"], new_key),
                    )
                for table in ("hud_sightings", "hud_actions", "hud_aliases"):
                    db.execute(
                        f"UPDATE {table} SET player_key=? WHERE player_key=?", (new_key, old_key)
                    )
                db.execute("DELETE FROM hud_players WHERE player_key=?", (old_key,))
            for alias in {player_key(old_name), old_key, new_key}:
                db.execute(
                    "INSERT INTO hud_aliases VALUES (?,?,?,?) ON CONFLICT(alias_key) "
                    "DO UPDATE SET player_key=excluded.player_key,evidence=excluded.evidence,"
                    "corrected_at=excluded.corrected_at",
                    (alias, new_key, json.dumps(evidence, ensure_ascii=False), now),
                )
        self.revision += 1

    def save(self, hand_id, table, source, seats, size, hero_seen, confirmed, evidence):
        if not re.fullmatch(r"\d{8,14}", hand_id):
            raise ValueError("Нужен номер раздачи из клиента")
        hero_roi = evidence.get("hero_roi")
        if evidence.get("hero_seat", 6) != 6 and not hero_roi:
            raise ValueError("Нужна область выбранного места героя")
        now = datetime.now(UTC).isoformat()
        hand_key = f"pokerdom:{table}:{hand_id}"
        with self.connection as db:
            db.execute(
                "INSERT INTO hud_hands VALUES (?,?,?,?,?,?) "
                "ON CONFLICT(hand_key) DO UPDATE SET "
                "hero_seen=MAX(hero_seen,excluded.hero_seen), "
                "confirmed=MAX(confirmed,excluded.confirmed)",
                (hand_key, hand_id, table, now, bool(hero_seen), bool(confirmed)),
            )
            names = [s.name.casefold() for s in seats if s.name and not s.missing]
            for seat in seats:
                x, y, w, h = seat.observation.roi
                # Tracker keys are not physical seats. Match the current plaque;
                # use historical central geometry only for legacy central captures.
                is_hero = (
                    math.dist((x, y), hero_roi[:2]) < hero_roi[2] * 0.6
                    if hero_roi
                    else 0.35 < (x + w / 2) / size[0] < 0.65 and (y + h / 2) / size[1] > 0.75
                )
                if is_hero:
                    continue
                if seat.missing:
                    continue
                trusted = bool(
                    seat.name
                    and not seat.conflict
                    and names.count(seat.name.casefold()) == 1
                    and (
                        seat.manual
                        or (seat.confirmations >= 2 and seat.observation.confidence >= 90)
                    )
                )
                canonical = self.resolve_name(seat.name)[0] if seat.name else ""
                key = player_key(canonical) if trusted else None
                if key:
                    db.execute(
                        "INSERT INTO hud_players VALUES (?,?,?,'',?,?) "
                        "ON CONFLICT(player_key) DO UPDATE SET last_seen=excluded.last_seen",
                        (key, "pokerdom", canonical, now, now),
                    )
                payload = {
                    **evidence,
                    "observation": seat.observation.to_dict(),
                    "manual": seat.manual,
                    "conflict": seat.conflict,
                }
                db.execute(
                    "INSERT INTO hud_sightings VALUES (?,?,?,?,?,?) "
                    "ON CONFLICT(hand_key,source,seat) DO UPDATE SET "
                    "player_key=CASE WHEN ? THEN NULL ELSE "
                    "COALESCE(excluded.player_key,hud_sightings.player_key) END,"
                    "raw_name=excluded.raw_name,"
                    "evidence=excluded.evidence",
                    (
                        hand_key,
                        source,
                        seat.key,
                        key,
                        seat.observation.raw_name,
                        json.dumps(payload, ensure_ascii=False),
                        bool(
                            seat.conflict or (seat.name and names.count(seat.name.casefold()) > 1)
                        ),
                    ),
                )
        self.revision += 1
        return hand_key

    def summary(self, name):
        key = player_key(self.resolve_name(name)[0])
        db = self.connection
        player = db.execute("SELECT note FROM hud_players WHERE player_key=?", (key,)).fetchone()
        hands = db.execute(
            "SELECT COUNT(DISTINCT s.hand_key) FROM hud_sightings s "
            "JOIN hud_hands h ON h.hand_key=s.hand_key "
            "WHERE s.player_key=? AND h.hero_seen=1 AND h.confirmed=1",
            (key,),
        ).fetchone()[0]
        rows = db.execute(
            "SELECT a.action,COUNT(*) FROM hud_actions a JOIN hud_hands h "
            "ON h.hand_key=a.hand_key WHERE a.player_key=? AND h.confirmed=1 "
            "AND h.hero_seen=1 GROUP BY a.action",
            (key,),
        ).fetchall()
        action_hands = db.execute(
            "SELECT COUNT(DISTINCT a.hand_key) FROM hud_actions a "
            "JOIN hud_hands h ON h.hand_key=a.hand_key WHERE a.player_key=? "
            "AND h.confirmed=1 AND h.hero_seen=1",
            (key,),
        ).fetchone()[0]
        return {
            "hands": hands,
            "style": describe_style(dict(rows), action_hands),
            "note": player["note"] if player else "",
        }

    def set_note(self, name, note):
        name = self.resolve_name(name)[0]
        now = datetime.now(UTC).isoformat()
        with self.connection as db:
            db.execute(
                "INSERT INTO hud_players VALUES (?,?,?,?,?,?) "
                "ON CONFLICT(player_key) DO UPDATE SET note=excluded.note",
                (player_key(name), "pokerdom", name.strip(), note[:2000], now, now),
            )
        self.revision += 1

    def record_action(self, event_id, hand_key, name, action, source, evidence):
        """Future verified recognizers/manual import feed this; raw OCR never does."""
        name = self.resolve_name(name)[0]
        if action not in {"fold", "check", "call", "bet", "raise"}:
            raise ValueError("Неизвестное действие")
        if source not in {"manual", "hand_history", "verified_vision"} or not evidence:
            raise ValueError("Нужен подтверждённый источник с доказательством")
        with self.connection as db:
            participant = db.execute(
                "SELECT 1 FROM hud_sightings s JOIN hud_hands h ON h.hand_key=s.hand_key "
                "WHERE s.hand_key=? AND s.player_key=? AND h.confirmed=1 AND h.hero_seen=1",
                (hand_key, player_key(name)),
            ).fetchone()
            if not participant:
                raise ValueError("Игрок не подтверждён в этой совместной раздаче")
            previous = db.execute(
                "SELECT hand_key,player_key,action FROM hud_actions WHERE event_id=?", (event_id,)
            ).fetchone()
            if previous and tuple(previous) != (hand_key, player_key(name), action):
                raise ValueError("Этот идентификатор уже принадлежит другому событию")
            db.execute(
                "INSERT OR IGNORE INTO hud_actions VALUES (?,?,?,?,?,?)",
                (
                    event_id,
                    hand_key,
                    player_key(name),
                    action,
                    source,
                    json.dumps(evidence, ensure_ascii=False),
                ),
            )
        self.revision += 1

    def backup(self, destination):
        destination = Path(destination).resolve()
        if destination == self.path or destination.exists():
            raise ValueError("Для копии нужен новый файл")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(destination)) as target:
            self.connection.backup(target)
        return destination

    def close(self):
        self.connection.close()


class LiveCollector:
    def __init__(self, store, source):
        self.store, self.source = store, source
        self.candidate = None
        self.readings = 0
        self.last_frame = None
        self.current = None
        self.status = "Статистика: ждём номер раздачи"

    def observe(self, context, table_state, metadata):
        metadata = hero_source(context, metadata)
        if metadata is None:
            self.current = self.candidate = None
            self.readings = 0
            self.status = "Статистика: место героя не подтверждено"
            return
        identity = context.get("hand_id", {})
        hand_id = identity.get("value", "")
        frame = metadata.get("frame_id", metadata.get("captured_at"))
        table_match = re.search(r"#(\d+)", metadata.get("window", ""))
        table = table_match.group(1) if table_match else metadata.get("window", "table")[:128]
        candidate = (table, hand_id)
        if not hand_id or identity.get("confidence", 0) < 80:
            self.current = None
            self.candidate = None
            self.readings = 0
            self.status = "Статистика: номер раздачи не прочитан"
            return
        if candidate != self.candidate:
            self.candidate, self.readings = candidate, 0
            self.last_frame = None
        if frame != self.last_frame:
            self.readings += 1
            self.last_frame = frame
        self.current = (context, metadata)
        hero_seen = context.get("hero_visible", False)
        self.store.save(
            hand_id,
            table,
            self.source,
            list(table_state.seats.values()),
            table_state.size,
            hero_seen,
            self.readings >= 2,
            metadata,
        )
        self.status = (
            f"Статистика: рука #{hand_id}"
            if self.readings >= 2
            else f"Статистика: подтверждаем #{hand_id}"
        )

    def correct_current(self, table_state):
        if self.current:
            context, metadata = self.current
            captured_at = metadata.get("captured_at")
            if (
                captured_at
                and (datetime.now(UTC) - datetime.fromisoformat(captured_at)).total_seconds() > 15
            ):
                return  # Await a fresh frame instead of editing a stale hand after a long pause.
            self.observe(context, table_state, metadata)
