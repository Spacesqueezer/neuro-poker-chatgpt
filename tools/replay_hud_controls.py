"""Audit live action controls on saved images, without model calls."""

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

import cv2

from poker.hud.recognition import configure_ocr
from poker.hud.session_images import saved_frame_path
from poker.hud.table_signals import controls


def select_frames(events, all_frames=False, first=None, last=None):
    """Keep exact capture metadata; never borrow context from a nearby OCR frame."""
    selected = {}
    for row in events:
        if row["kind"] not in ({"frame", "names"} if all_frames else {"names"}):
            continue
        number = row["frame_id"]
        if (first is not None and number < first) or (last is not None and number > last):
            continue
        key = (number, row["captured_at"])
        if key not in selected or row["kind"] == "names":
            selected[key] = row
    return sorted(selected.values(), key=lambda r: r["captured_at"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session", type=Path)
    parser.add_argument("--output", type=Path, default=Path("artifacts/hud/control_replays"))
    parser.add_argument(
        "--all-frames", action="store_true", help="Include saved frames between name OCR jobs"
    )
    parser.add_argument("--first-frame", type=int)
    parser.add_argument("--last-frame", type=int)
    args = parser.parse_args()
    if (
        args.first_frame is not None
        and args.last_frame is not None
        and args.first_frame > args.last_frame
    ):
        parser.error("--first-frame must not exceed --last-frame")
    configure_ocr()
    output = args.output / datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    output.mkdir(parents=True)
    events = []
    inputs = sorted(args.session.glob("events.jsonl*"))
    for path in inputs:
        events += [
            r
            for line in path.read_text(encoding="utf8").splitlines()
            if (r := json.loads(line))["kind"] in {"names", "frame"}
        ]
    counts = Counter()
    lines = [
        "# Проверка кнопок действий",
        "",
        "Выбранная сумма рейза не является его допустимой границей.",
        "",
    ]
    with (output / "observations.jsonl").open("w", encoding="utf8") as stream:
        for row in select_frames(events, args.all_frames, args.first_frame, args.last_frame):
            path = saved_frame_path(args.session, row["frame_id"])
            if not path.exists():
                counts["missing_images"] += 1
                continue
            old = row.get("context", {}).get("table_signals", {}).get("controls", {})
            current = controls(cv2.imread(str(path)))
            counts["images"] += 1
            counts["old_active"] += bool(old.get("flags"))
            counts["active"] += bool(current["flags"])
            counts["old_call_known"] += (
                bool(old.get("flags")) and old.get("call_amount") is not None
            )
            counts["call_known"] += bool(current["flags"]) and current["call_amount"] is not None
            counts["selected_wager_known"] += current["selected_wager"] is not None
            record = {
                "frame_id": row["frame_id"],
                "captured_at": row["captured_at"],
                "source_kind": row["kind"],
                "client_rect": row.get("client_rect"),
                "window": row.get("window"),
                "image": str(path.resolve()),
                "old": old,
                "controls": current,
            }
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            if current["flags"]:
                selected = current["selected_wager"]
                lines.append(
                    f"- [Кадр {row['frame_id']}]({path.resolve().as_posix()}): "
                    f"колл {current['call_amount']}; выбранная сумма "
                    f"{selected['value'] if selected else 'неизвестна'}; границы рейза неизвестны."
                )
            if counts["images"] % 100 == 0:
                print(f"{counts['images']} frames", flush=True)
    sources = [Path(__file__), Path("src/poker/hud/table_signals.py")]
    summary = {
        "schema_version": 1,
        "session": args.session.name,
        "all_frames": args.all_frames,
        "first_frame": args.first_frame,
        "last_frame": args.last_frame,
        **counts,
        "input_sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
        "source_sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        "model_called": False,
    }
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf8"
    )
    (output / "review.md").write_text("\n".join(lines), encoding="utf8")
    print(json.dumps(summary), flush=True)
    print(output.resolve(), flush=True)


if __name__ == "__main__":
    main()
