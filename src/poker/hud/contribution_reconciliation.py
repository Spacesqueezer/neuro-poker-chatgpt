"""Offline reconciliation of repeated stack/bet endpoints, never complete hand totals."""

import re
from copy import deepcopy
from datetime import datetime

from poker.learning.advisor_contract import minor_units


def reconcile_observations(rows, *, quantum="0.01"):
    """Compare stack decrease with visible street-bet increase within one street.

    Missing intermediate amounts are allowed but explicitly mark an incomplete
    interval. A balanced interval proves only arithmetic consistency of readings,
    not action ordering, forced payments, refunds or a complete contribution.
    Caller supplies events in arrival order; future/out-of-order captures are ignored.
    """
    points, intervals = [], []
    candidates, previous, missing = {}, {}, set()
    boundary = None
    last = None
    skipped = 0
    for row in rows:
        if row.get("kind") in {"target", "window", "pause"}:
            candidates.clear()
            previous.clear()
            missing.clear()
            boundary = None
            continue
        if row.get("kind", "names") != "names":
            continue
        try:
            at = datetime.fromisoformat(row["captured_at"])
            frame = row["frame_id"]
        except (ValueError, TypeError, KeyError):
            candidates.clear()
            previous.clear()
            missing.clear()
            skipped += 1
            continue
        if last and (at <= last[0] or frame == last[1]):
            skipped += 1
            continue
        context = row.get("context", {})
        identity = context.get("hand_id", {})
        hand = str(identity.get("value", ""))
        board = tuple(context.get("decision_hand", {}).get("board", ()))
        slots = context.get("table_signals", {}).get("slots", [])
        key = (
            hand,
            board,
            row.get("window"),
            tuple(row.get("client_rect", [])),
            row.get("evidence_epoch"),
        )
        valid = (
            re.fullmatch(r"\d{8,14}", hand)
            and identity.get("confidence", 0) >= 80
            and row.get("window") is not None
            and len(row.get("client_rect", [])) == 4
            and len(board) in (0, 3, 4, 5)
            and len(set(board)) == len(board)
            and all(re.fullmatch(r"[2-9TJQKA][shdc]", c) for c in board)
            and [s.get("seat_index") for s in slots] == list(range(7))
            and not any(s.get("settlement_label") for s in slots)
        )
        if key != boundary or not valid or (last and (at - last[0]).total_seconds() > 10):
            candidates.clear()
            previous.clear()
            missing.clear()
        boundary, last = key, (at, frame)
        if not valid:
            continue
        source = {
            k: deepcopy(row.get(k))
            for k in ("frame_id", "captured_at", "image", "window", "client_rect", "evidence_epoch")
        }
        try:
            source["observed_pot"] = minor_units(
                context.get("table_signals", {}).get("pot", {}).get("value"), quantum
            )
        except (ValueError, TypeError):
            source["observed_pot"] = None
        readings = context.get("stack_readings", {})
        for slot in slots:
            seat = slot["seat_index"]
            stack = readings.get(str(seat), readings.get(seat, {}))
            try:
                values = (
                    minor_units(stack.get("value"), quantum),
                    minor_units(slot.get("current_bet"), quantum),
                )
            except (ValueError, TypeError):
                values = (None, None)
            if None in values:
                candidates.pop(seat, None)
                missing.add(seat)
                continue
            old = candidates.get(seat)
            candidates[seat] = values, at, source
            if not old or old[0] != values or (at - old[1]).total_seconds() > 5:
                continue
            point = dict(
                hand_id=hand,
                seat=seat,
                board=list(board),
                stack=values[0],
                street_bet=values[1],
                pot=source["observed_pot"]
                if source["observed_pot"] == old[2]["observed_pot"]
                else None,
                confirmation_frames=[old[2], source],
            )
            before = previous.get(seat)
            previous[seat] = point
            if before and (before["stack"], before["street_bet"]) == values:
                missing.discard(seat)
                continue
            points.append(deepcopy(point))
            if before:
                elapsed = (
                    at - datetime.fromisoformat(before["confirmation_frames"][-1]["captured_at"])
                ).total_seconds()
                if elapsed <= 30:
                    stack_drop = before["stack"] - point["stack"]
                    bet_growth = point["street_bet"] - before["street_bet"]
                    residual = stack_drop - bet_growth
                    intervals.append(
                        dict(
                            hand_id=hand,
                            seat=seat,
                            before=deepcopy(before),
                            after=deepcopy(point),
                            stack_decrease=stack_drop,
                            street_bet_increase=bet_growth,
                            residual=residual,
                            status="balanced_observed_endpoints"
                            if residual == 0
                            else "amount_mismatch",
                            missing_intermediate_readings=seat in missing,
                            possible_return_or_correction=stack_drop < 0 or bet_growth < 0,
                            contributed_delta=None,
                            hand_contribution=None,
                            history_complete=False,
                        )
                    )
            missing.discard(seat)
    return dict(
        schema_version=1,
        quantum=quantum,
        points=points,
        intervals=intervals,
        skipped_out_of_order_or_invalid=skipped,
        semantics="endpoint_consistency_not_action_labels",
        model_called=False,
        player_db_written=False,
    )
