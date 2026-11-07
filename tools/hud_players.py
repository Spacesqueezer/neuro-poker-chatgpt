"""Inspect, back up, and import local captures into the live HUD database."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from poker.hud.player_store import LiveCollector, PlayerStore  # noqa: E402
from poker.hud.state import TableState  # noqa: E402


def import_captures(store, root):
    import cv2

    from poker.hud.cards import find_cards
    from poker.hud.client_id import read_hand_id
    from poker.hud.recognition import analyze, configure_ocr

    configure_ocr()
    source = "import:" + hashlib.sha256(str(root.resolve()).encode()).hexdigest()[:24]
    collector, state = LiveCollector(store, source), TableState()
    count = 0
    for path in sorted(root.glob("*/table.png")):
        frame = cv2.imread(str(path))
        if frame is None:
            raise OSError(f"Cannot read {path}")
        metadata_path = path.parent / "capture.json"
        if not metadata_path.exists():
            continue
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        state.update(analyze(frame), (frame.shape[1], frame.shape[0]))
        context = {
            "hand_id": read_hand_id(frame),
            "hero_visible": sum(c.zone == "hero" for c in find_cards(frame)) == 2,
        }
        collector.observe(
            context,
            state,
            {
                "frame_id": path.parent.name,
                "window": metadata.get("window", ""),
                "image": str(path.resolve()),
                "captured_at": metadata.get("captured_at", metadata.get("saved_at")),
            },
        )
        count += 1
    return count


def export_players(store, destination):
    rows = store.connection.execute(
        "SELECT display_name,first_seen,last_seen FROM hud_players ORDER BY display_name"
    ).fetchall()
    players = [{**dict(row), **store.summary(row["display_name"])} for row in rows]
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "players.json").write_text(
        json.dumps({"schema_version": 1, "players": players}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    lines = [
        "# Наблюдения за игроками",
        "",
        "Руки — совместно наблюдённые раздачи, а не полная история сыгранных рук.",
        "",
        "| Игрок | Рук | Описание | Моя заметка |",
        "| --- | ---: | --- | --- |",
    ]
    for player in players:
        values = [player["display_name"], str(player["hands"]), player["style"], player["note"]]
        lines.append(
            "| " + " | ".join(v.replace("|", "\\|").replace("\n", " ") for v in values) + " |"
        )
    (destination / "players.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return players


def main():
    parser = argparse.ArgumentParser(description="Статистика игроков HUD в переносимой SQLite")
    parser.add_argument("--database", type=Path, default=PROJECT / "data/hud/players.sqlite3")
    parser.add_argument("--import-captures", type=Path)
    parser.add_argument("--backup", type=Path, help="Новый файл для резервной копии")
    parser.add_argument("--export", type=Path, default=PROJECT / "artifacts/hud/players")
    args = parser.parse_args()
    store = PlayerStore(args.database)
    try:
        if args.import_captures:
            print(f"Processed captures: {import_captures(store, args.import_captures)}")
        if args.backup:
            print(f"Backup: {store.backup(args.backup)}")
        players = export_players(store, args.export)
        print(f"Players: {len(players)}; report: {args.export / 'players.md'}")
    finally:
        store.close()


if __name__ == "__main__":
    main()
