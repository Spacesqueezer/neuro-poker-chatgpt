"""Retrospective stack changes around captions, never verified action amounts."""

import re
from copy import deepcopy
from datetime import datetime, timedelta

from poker.learning.advisor_contract import minor_units


def _key(row):
    context = row.get("context", {})
    identity = context.get("hand_id", {})
    hand = str(identity.get("value", ""))
    slots = context.get("table_signals", {}).get("slots", [])
    rect = row.get("client_rect") or []
    if (
        not re.fullmatch(r"\d{8,14}", hand)
        or identity.get("confidence", 0) < 80
        or type(row.get("frame_id")) is not int
        or row.get("window") is None
        or len(rect) != 4
        or [s.get("seat_index") for s in slots] != list(range(7))
        or any(s.get("settlement_label") for s in slots)
    ):
        return None
    return hand, row["window"], tuple(rect), row.get("evidence_epoch")


def _segments(rows):
    segment, key, last = [], None, None
    for row in rows:
        if row.get("kind") in {"target", "window", "pause"}:
            if segment:
                yield segment
            segment, key = [], None
            continue
        if row.get("kind", "names") != "names":
            continue
        try:
            at = datetime.fromisoformat(row["captured_at"])
        except (KeyError, TypeError, ValueError):
            if segment:
                yield segment
            segment, key = [], None
            continue
        if last and (at <= last[0] or row.get("frame_id") == last[1]):
            continue
        current = _key(row)
        if current != key or current is None or (last and (at - last[0]).total_seconds() > 5):
            if segment:
                yield segment
            segment = []
        last, key = (at, row.get("frame_id")), current
        if current is not None:
            segment.append((at, row))
    if segment:
        yield segment


def _points(segment, seat, quantum):
    previous = None
    result = []
    for _at, row in segment:
        readings = row["context"].get("stack_readings", {})
        try:
            value = minor_units(
                readings.get(str(seat), readings.get(seat, {})).get("value"), quantum
            )
        except (ValueError, TypeError):
            value = None
        source = {k: deepcopy(row.get(k)) for k in ("frame_id", "captured_at", "image")}
        source["board"] = deepcopy(row["context"].get("decision_hand", {}).get("board"))
        if value is not None and previous and previous[0] == value:
            result.append(dict(stack=value, confirmation_frames=[previous[1], source]))
        previous = (value, source) if value is not None else None
    return result


def audit_action_stacks(rows, hands, quantum="0.01"):
    """Both endpoints need two reads. Cross-street pairs remain unverified candidates."""
    actions = [
        (str(hand["hand_id"]), e)
        for hand in hands
        for e in hand["events"]
        if e["kind"] == "action_label" and e["action"] in {"call", "bet", "raise", "all_in"}
    ]
    results = []
    for segment in _segments(rows):
        sources = {(r["frame_id"], r["captured_at"]): r for _, r in segment}
        local = [
            e
            for hand, e in actions
            if hand == _key(segment[0][1])[0] and (e["frame_id"], e["captured_at"]) in sources
        ]
        points = {}
        for action in local:
            seat = action["seat_index"]
            row = sources[action["frame_id"], action["captured_at"]]
            slot = row["context"]["table_signals"]["slots"][seat]
            label = slot.get("action_label") or {}
            words = label.get("words", [])
            if (
                label.get("action") != action["action"]
                or not words
                or min(w["confidence"] for w in words) < 85
                or slot.get("action_sampled") is False
            ):
                continue
            if seat not in points:
                points[seat] = _points(segment, seat, quantum)
            at = datetime.fromisoformat(action["captured_at"])
            before, after = [], []
            for point in points[seat]:
                first, last = [
                    datetime.fromisoformat(s["captured_at"]) for s in point["confirmation_frames"]
                ]
                if 0 < (at - last).total_seconds() <= 5:
                    before.append(point)
                elif first >= at and 0 < (last - at).total_seconds() <= 5:
                    after.append(point)
            if not before or not after:
                continue
            left, right = before[-1], after[0]
            low = left["confirmation_frames"][0]["captured_at"]
            high = right["confirmation_frames"][-1]["captured_at"]
            competitors = [
                e
                for e in local
                if e is not action
                and e["seat_index"] == seat
                and datetime.fromisoformat(low)
                <= datetime.fromisoformat(e["captured_at"])
                <= datetime.fromisoformat(high)
            ]
            decrease = left["stack"] - right["stack"]
            results.append(
                dict(
                    hand_id=_key(row)[0],
                    seat=seat,
                    action=deepcopy(action),
                    before=left,
                    after=right,
                    stack_decrease=decrease,
                    confirmation_timing={
                        "last_evidence_captured_at": high,
                        "capture_span_after_action_ms": (datetime.fromisoformat(high) - at)
                        // timedelta(milliseconds=1),
                        "before_evidence_age_ms": (
                            at
                            - datetime.fromisoformat(left["confirmation_frames"][-1]["captured_at"])
                        )
                        // timedelta(milliseconds=1),
                        "processing_latency_ms": None,
                    },
                    status="competing_actions" if competitors else "observed_stack_change",
                    competing_actions=deepcopy(competitors),
                    contributed_delta=None,
                    hand_contribution=None,
                    uses_later_evidence=True,
                    verified_for_training=False,
                    verified_for_statistics=False,
                )
            )
    return results
