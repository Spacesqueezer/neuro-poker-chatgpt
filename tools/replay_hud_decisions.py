"""Replay saved name-source frames into an isolated offline request recording."""

import argparse
import json
from datetime import datetime
from pathlib import Path

import cv2

from poker.hud.cards import find_cards
from poker.hud.decision_stream import DecisionStream, blocker_comment, proposal
from poker.hud.diagnostics import Recorder
from poker.hud.hand import observe
from poker.hud.models import PlayerObservation
from poker.hud.pipeline import my_turn
from poker.hud.recognition import configure_ocr
from poker.hud.session_images import saved_frame_path
from poker.hud.state import TableState
from poker.hud.table_signals import analyze_table


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session", type=Path)
    parser.add_argument("--output", type=Path, default=Path("artifacts/hud/replays"))
    args = parser.parse_args()
    configure_ocr()
    rows = [
        json.loads(line)
        for path in args.session.glob("events.jsonl*")
        for line in path.read_text(encoding="utf8").splitlines()
        if line.strip()
    ]
    rows.sort(key=lambda r: r["at"])
    recorder, stream, state = Recorder(args.output), DecisionStream(), TableState()
    processed = turns = missing = 0
    try:
        for row in rows:
            if row["kind"] in {"target", "window", "pause"}:
                stream.reset()
            if row["kind"] != "names":
                continue
            path = saved_frame_path(args.session, row["frame_id"])
            frame = cv2.imread(str(path)) if path.exists() else None
            if frame is None:
                missing += 1
                stream.reset()
                continue
            processed += 1
            state.update(
                [PlayerObservation(**p) for p in row["players"]], (frame.shape[1], frame.shape[0])
            )
            if not my_turn(frame):
                stream.reset()
                continue
            turns += 1
            context = dict(row.get("context", {}))
            context["table_signals"] = analyze_table(
                frame, context.get("regions", {}), context.get("dealer_candidates", [])
            )
            hand = observe(find_cards(frame), True)
            meta = {key: row[key] for key in ("frame_id", "captured_at", "window", "client_rect")}
            identity = row.get("context", {}).get("hand_id", {})
            result = stream.update(
                proposal(hand, state.seats.values(), context),
                meta,
                identity.get("value", "") if identity.get("confidence", 0) >= 80 else "",
                cards_valid=hand.valid,
                blockers=("table_membership_unverified", "betting_state_unverified"),
                now=datetime.fromisoformat(meta["captured_at"]),
            )
            if result:
                recorder.event(
                    "decision_dry_run",
                    {
                        **meta,
                        **result,
                        "original_session": str(args.session.resolve()),
                        "original_image": str(path.resolve()),
                        "replay": True,
                        "context": context,
                        "players_evidence": row["players"],
                    },
                    "Повторный разбор: запрос заблокирован — "
                    + blocker_comment(result["blockers"]),
                    frame=frame,
                )
    finally:
        recorder.close()
    if recorder.error or recorder.dropped:
        raise RuntimeError(f"Recording incomplete: {recorder.error}; dropped={recorder.dropped}")
    summary = {
        "frames": processed,
        "my_turn_frames": turns,
        "missing_frames": missing,
        "proposals": getattr(recorder, "request_count", 0),
        "output": str(recorder.path),
    }
    (recorder.path / "replay_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf8"
    )
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
