"""Repeated pot changes with context, never automatic rake/return/award labels."""

import re
from copy import deepcopy
from datetime import datetime

from poker.learning.advisor_contract import minor_units


def pot_movements(rows, quantum="0.01"):
    candidate = baseline = boundary = last = None
    trail = []
    movements = []
    for row in rows:
        if row.get("kind") in {"target", "window", "pause"}:
            candidate = baseline = boundary = None
            trail = []
            continue
        if row.get("kind", "names") != "names":
            continue
        try:
            at = datetime.fromisoformat(row["captured_at"])
        except (KeyError, TypeError, ValueError):
            candidate = baseline = boundary = None
            trail = []
            continue
        frame = row.get("frame_id")
        if last and (at <= last[0] or frame == last[1]):
            continue
        context = row.get("context", {})
        identity = context.get("hand_id", {})
        hand = str(identity.get("value", ""))
        key = (
            hand,
            row.get("window"),
            tuple(row.get("client_rect", [])),
            row.get("evidence_epoch"),
        )
        valid = (
            bool(re.fullmatch(r"\d{8,14}", hand))
            and identity.get("confidence", 0) >= 80
            and row.get("window") is not None
            and len(row.get("client_rect", [])) == 4
        )
        if key != boundary or not valid or (last and (at - last[0]).total_seconds() > 5):
            candidate = baseline = None
            trail = []
        boundary, last = key, (at, frame)
        if not valid:
            continue
        signals = context.get("table_signals", {})
        slots = signals.get("slots", [])
        source = {k: deepcopy(row.get(k)) for k in ("frame_id", "captured_at", "image")}
        source.update(
            board=deepcopy(context.get("decision_hand", {}).get("board", [])),
            folds=[
                s["seat_index"]
                for s in slots
                if (s.get("action_label") or {}).get("action") == "fold"
            ],
            settlements=[s["seat_index"] for s in slots if s.get("settlement_label")],
        )
        trail.append((at, source))
        trail = [(t, s) for t, s in trail if (at - t).total_seconds() <= 10]
        try:
            value = minor_units(signals.get("pot", {}).get("value"), quantum)
        except (ValueError, TypeError):
            value = None
        if value is None:
            candidate = None
            continue
        old = candidate
        candidate = (value, at, source)
        if not old or old[0] != value or (at - old[1]).total_seconds() > 5:
            continue
        point = dict(value=value, confirmation_frames=[old[2], source])
        if baseline and baseline["value"] != value:
            start = datetime.fromisoformat(baseline["confirmation_frames"][-1]["captured_at"])
            if (at - start).total_seconds() <= 10:
                movements.append(
                    dict(
                        hand_id=hand,
                        before=deepcopy(baseline),
                        after=deepcopy(point),
                        delta=value - baseline["value"],
                        direction="decrease" if value < baseline["value"] else "increase",
                        context_frames=[deepcopy(s) for t, s in trail if start <= t <= at],
                        cause="unclassified",
                        rake=None,
                        returned_amount=None,
                        award=None,
                        verified_for_training=False,
                        verified_for_statistics=False,
                    )
                )
        baseline = point
    return movements
