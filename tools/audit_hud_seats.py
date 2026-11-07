"""Replay seat evidence without changing requests, player profiles or statistics."""

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

import cv2

from poker.hud.hand_reconstruction import HandReconstructor
from poker.hud.seat_evidence import participation
from poker.hud.seat_occupancy import EmptySeatTracker, read_dim_status, read_empty_seat

if __package__:
    from .replay_hud_hands import cached_rows
else:
    from replay_hud_hands import cached_rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session", type=Path)
    parser.add_argument("observations", type=Path)
    parser.add_argument("--output", type=Path, default=Path("artifacts/hud/seat_audits"))
    args = parser.parse_args()
    output = args.output / datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    output.mkdir(parents=True)
    empty, hands = EmptySeatTracker(), HandReconstructor()
    counts = Counter()
    lines = [
        "# Текущие места и участие в раздаче",
        "",
        "Пустое место не означает, что игрок не участвовал раньше. "
        "Отсутствие карт не доказывает сброс.",
        "",
    ]
    with (output / "observations.jsonl").open("w", encoding="utf8") as stream:
        for row in cached_rows(args.session, args.observations):
            if row["kind"] != "frame":
                empty = EmptySeatTracker()
                hands.interrupt("capture_boundary")
                continue
            hands.update(row)
            facts = participation(hands)
            slots = row["context"]["table_signals"].get("slots", [])
            frame = cv2.imread(row["image"])
            if frame is None:
                raise ValueError(f"Missing frame: {row['image']}")
            readings = {s["seat_index"]: read_empty_seat(frame, s["roi"]) for s in slots}
            occupied = {
                s["seat_index"]
                for s in slots
                if s.get("card_back_evidence", {}).get("present") is True
            }
            hero = row["context"].get("decision_hand", {})
            if hero.get("valid") and len(hero.get("hero", [])) == 2:
                occupied.add(6)
            confirmed = empty.update(row, readings, occupied)
            states = {}
            for slot in slots:
                seat = slot["seat_index"]
                fact = facts.get(seat, {})
                status = read_dim_status(frame, slot["roi"])
                state = (
                    "empty"
                    if seat in confirmed
                    else "active"
                    if fact.get("is_active") is True
                    else "folded"
                    if fact.get("is_active") is False
                    else "sitting_out"
                    if status and seat not in occupied
                    else "unknown"
                )
                states[seat] = {
                    "state": state,
                    "seat_status": status,
                    "empty_evidence": confirmed.get(seat),
                    "hand_participation": fact,
                }
                counts[state] += 1
            counts["frames"] += 1
            stream.write(
                json.dumps(
                    {
                        "frame_id": row["frame_id"],
                        "captured_at": row["captured_at"],
                        "image": row["image"],
                        "states": states,
                        "icon_readings": readings,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            if confirmed:
                seats = ", ".join(str(s + 1) for s in confirmed)
                lines.append(
                    f"- [Кадр {row['frame_id']}]({Path(row['image']).as_posix()}): "
                    f"пустые места {seats}; подтверждены двумя кадрами."
                )
    summary = {
        "schema_version": 1,
        "counts": dict(counts),
        "model_called": False,
        "statistics_written": False,
        "input_sha256": hashlib.sha256(args.observations.read_bytes()).hexdigest(),
        "status_template_sha256": hashlib.sha256(
            Path("src/poker/hud/sitting_out_template.json").read_bytes()
        ).hexdigest(),
        "template_sha256": hashlib.sha256(
            Path("src/poker/hud/empty_seat_template.json").read_bytes()
        ).hexdigest(),
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf8")
    (output / "review.md").write_text("\n".join(lines), encoding="utf8")
    print(json.dumps(summary), flush=True)
    print(output.resolve(), flush=True)


if __name__ == "__main__":
    main()
