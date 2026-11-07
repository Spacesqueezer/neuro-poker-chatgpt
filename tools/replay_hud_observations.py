"""Refresh exact-frame HUD observations offline; no model or player DB writes."""

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

import cv2

from poker.hud.context import analyze_names
from poker.hud.recognition import configure_ocr
from poker.hud.session_images import saved_frame_path

if __package__:
    from .replay_hud_controls import select_frames
else:
    from replay_hud_controls import select_frames


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session", type=Path)
    parser.add_argument("--output", type=Path, default=Path("artifacts/hud/observation_replays"))
    args = parser.parse_args()
    configure_ocr()
    inputs = sorted(args.session.glob("events.jsonl*"))
    events = [
        json.loads(line)
        for path in inputs
        for line in path.read_text(encoding="utf8").splitlines()
        if line.strip()
    ]
    output = args.output / datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    output.mkdir(parents=True)
    sources = [Path(__file__), *Path("src/poker/hud").glob("*.py")]
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    counts = Counter()
    print(output.resolve(), flush=True)
    with (
        (output / "observations.jsonl").open("w", encoding="utf8") as observations,
        (output / "controls.jsonl").open("w", encoding="utf8") as controls,
    ):
        for row in select_frames(events, False, None, None):
            path = saved_frame_path(args.session, row["frame_id"])
            image = cv2.imread(str(path)) if path.exists() else None
            if image is None:
                counts["missing_images"] += 1
                continue
            players, context = analyze_names(image)
            meta = {key: row[key] for key in ("frame_id", "captured_at", "window", "client_rect")}
            meta["image"] = str(path.resolve())
            observations.write(
                json.dumps(
                    {
                        **meta,
                        "players": [p.to_dict() for p in players],
                        "context": context,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            controls.write(
                json.dumps(
                    {
                        **meta,
                        "controls": context.get("table_signals", {}).get("controls", {}),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            observations.flush()
            controls.flush()
            counts["images"] += 1
            counts["error_frames"] += bool(context["errors"])
            counts["valid_cards"] += context["decision_hand"]["valid"]
            if counts["images"] % 20 == 0:
                print(dict(counts), flush=True)
    summary = {
        "schema_version": 1,
        "session": str(args.session.resolve()),
        **counts,
        "model_called": False,
        "source_sha256": hashes,
        "input_sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
    }
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf8"
    )
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
