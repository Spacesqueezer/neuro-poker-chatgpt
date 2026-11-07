"""Audit blind labels against amounts on their exact confirmation frames."""

import math
from collections import Counter
from datetime import datetime


def audit_blinds(hands, observations):
    observations = list(observations)
    counts = Counter(row["frame_id"] for row in observations)
    rows = {row["frame_id"]: row for row in observations}
    result = []
    for hand in hands:
        for event in hand["events"]:
            if event["kind"] != "blind_label":
                continue
            evidence = []
            for source in event["confirmation_frames"]:
                row = rows.get(source["frame_id"], {})
                context = row.get("context", {})
                identity = context.get("hand_id", {})
                slots = context.get("table_signals", {}).get("slots", [])
                slot = next((s for s in slots if s["seat_index"] == event["seat_index"]), {})
                label = slot.get("blind_label") or {}
                value = slot.get("current_bet")
                words = label.get("words", [])
                matches = (
                    row.get("captured_at") == source["captured_at"]
                    and str(identity.get("value")) == str(hand["hand_id"])
                    and identity.get("confidence", 0) >= 80
                    and label.get("blind") == event["blind"]
                    and not slot.get("action_label")
                    and not slot.get("settlement_label")
                    and context.get("decision_hand", {}).get("board") == []
                    and bool(words)
                    and all(w.get("confidence", 0) >= 85 for w in words)
                    and counts[source["frame_id"]] == 1
                )
                known = (
                    matches and type(value) in (int, float) and math.isfinite(value) and value > 0
                )
                evidence.append(
                    {
                        **source,
                        "value": value if known else None,
                        "bet_evidence": slot.get("bet_evidence"),
                        "board": context.get("decision_hand", {}).get("board"),
                        "matching_blind_frame": matches,
                        "window": row.get("window"),
                        "client_rect": row.get("client_rect"),
                    }
                )
            values = [e["value"] for e in evidence]
            confirmed = (
                len(evidence) == 2
                and len({e["frame_id"] for e in evidence}) == 2
                and all(v is not None for v in values)
                and values[0] == values[1]
                and fresh_same_capture_pair(evidence)
            )
            conflict = len({v for v in values if v is not None}) > 1
            result.append(
                {
                    "schema_version": 1,
                    "hand_id": hand["hand_id"],
                    "seat_index": event["seat_index"],
                    "blind": event["blind"],
                    "status": "same_frame_amount_confirmed"
                    if confirmed
                    else "amount_conflict"
                    if conflict
                    else "amount_unknown",
                    "visible_amount": values[0] if confirmed else None,
                    "phase_hint": "blind_labels_visible",
                    "street": event.get("street"),
                    "evidence": evidence,
                    "amount_semantics": "visible_total_not_proven_forced_contribution",
                    "verified_for_statistics": False,
                }
            )
    big_blind_seats = {}
    for item in result:
        if item["blind"] == "big_blind" and item["visible_amount"] is not None:
            big_blind_seats.setdefault(item["hand_id"], set()).add(item["seat_index"])
    for item in result:
        item["hand_warnings"] = (
            ["multiple_big_blind_amounts_observed"]
            if len(big_blind_seats.get(item["hand_id"], ())) > 1
            else []
        )
    return result


def fresh_same_capture_pair(evidence):
    if len(evidence) != 2:
        return False
    first, second = evidence
    try:
        elapsed = (
            datetime.fromisoformat(second["captured_at"])
            - datetime.fromisoformat(first["captured_at"])
        ).total_seconds()
    except (ValueError, TypeError, KeyError):
        return False
    return (
        0 < elapsed <= 5
        and first.get("window") is not None
        and first["window"] == second.get("window")
        and bool(first.get("client_rect"))
        and first["client_rect"] == second.get("client_rect")
    )
