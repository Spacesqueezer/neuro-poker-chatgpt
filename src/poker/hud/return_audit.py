"""Offline return hypotheses from stacks, visible bets and repeated opposing folds."""

import re
from copy import deepcopy
from datetime import datetime

from poker.hud.action_stack_audit import _points, _segments
from poker.learning.advisor_contract import minor_units


def _amount(value, quantum):
    try:
        return minor_units(value, quantum)
    except (ValueError, TypeError):
        return None


def _fold(slot):
    label = slot.get("action_label") or {}
    words = label.get("words", [])
    return (
        slot.get("action_sampled") is not False
        and label.get("action") == "fold"
        and bool(words)
        and min(w["confidence"] for w in words) >= 85
    )


def _board(row):
    board = row["context"].get("decision_hand", {}).get("board")
    if (
        isinstance(board, (list, tuple))
        and all(isinstance(card, str) for card in board)
        and len(board) in {0, 3, 4, 5}
        and len(set(board)) == len(board)
        and all(re.fullmatch(r"[2-9TJQKA][shdc]", card) for card in board)
    ):
        return tuple(board)
    return None


def _earlier_street_folds(segment, before_rows, after_rows):
    """A repeated fold on an earlier street implies no contribution on this street."""
    board = _board(before_rows[0])
    if board is None or board != _board(before_rows[1]):
        return {}
    cutoff = datetime.fromisoformat(before_rows[0]["captured_at"])
    end = datetime.fromisoformat(after_rows[-1]["captured_at"])
    candidates, confirmed, conflicts = {}, {}, set()
    largest_board = 0
    for at, row in segment:
        if at > end:
            break
        current = _board(row)
        if current is not None:
            if current != board[: len(current)] or len(current) < largest_board:
                return {}  # A cleared/conflicting board does not prove a prior street.
            largest_board = len(current)
        for slot in row["context"]["table_signals"]["slots"]:
            seat = slot["seat_index"]
            if seat in confirmed and (
                (slot.get("action_label") or {}).get("action") not in {None, "fold"}
                or slot.get("blind_label")
                or (
                    slot.get("current_bet") not in (None, 0)
                    and (
                        at >= cutoff
                        or (
                            current is not None
                            and len(current)
                            > len(confirmed[seat]["confirmation_frames"][0]["board"])
                        )
                    )
                )
            ):
                conflicts.add(seat)
            if at > cutoff:
                continue
            if not (
                _fold(slot)
                and current is not None
                and len(current) < len(board)
                and current == board[: len(current)]
            ):
                candidates.pop(seat, None)
                continue
            source = {k: deepcopy(row.get(k)) for k in ("frame_id", "captured_at", "image")}
            source["board"] = list(current)
            previous = candidates.get(seat)
            if previous and previous["board"] == list(current):
                confirmed.setdefault(
                    seat,
                    dict(
                        method="repeated_fold_on_earlier_street",
                        inferred_street_bet=0,
                        confirmation_frames=[previous, source],
                    ),
                )
            candidates[seat] = source
    for seat in list(confirmed):
        slots = [r["context"]["table_signals"]["slots"][seat] for r in before_rows]
        # A conflicting current amount or action cannot be overridden by an old fold.
        if seat in conflicts or any(
            s.get("current_bet") not in (None, 0)
            or (s.get("action_label") or {}).get("action") not in {None, "fold"}
            or s.get("blind_label")
            for s in slots
        ):
            confirmed.pop(seat)
    return confirmed


def audit_returns(rows, quantum="0.01"):
    """Do not classify pot decreases or payout/next-hand stack increases as returns.

    Raw missing bets remain unknown; repeated earlier-street folds can separately
    account for zero on this street. Full contributions, payouts and fees stay unknown.
    """
    results = []
    for segment in _segments(rows):
        sources = {(r["frame_id"], r["captured_at"]): r for _, r in segment}
        for seat in range(7):
            points = _points(segment, seat, quantum)
            for before, after in zip(points, points[1:], strict=False):
                increase = after["stack"] - before["stack"]
                first = datetime.fromisoformat(before["confirmation_frames"][-1]["captured_at"])
                last = datetime.fromisoformat(after["confirmation_frames"][-1]["captured_at"])
                if increase <= 0 or (last - first).total_seconds() > 5:
                    continue
                old = [
                    sources[s["frame_id"], s["captured_at"]] for s in before["confirmation_frames"]
                ]
                new = [
                    sources[s["frame_id"], s["captured_at"]] for s in after["confirmation_frames"]
                ]
                old_slots = [r["context"]["table_signals"]["slots"] for r in old]
                new_slots = [r["context"]["table_signals"]["slots"] for r in new]
                old_pots = [
                    _amount(r["context"]["table_signals"].get("pot", {}).get("value"), quantum)
                    for r in old
                ]
                new_pots = [
                    _amount(r["context"]["table_signals"].get("pot", {}).get("value"), quantum)
                    for r in new
                ]
                if (
                    None in old_pots + new_pots
                    or old_pots[0] != old_pots[1]
                    or any(value > old_pots[0] - increase for value in new_pots)
                ):
                    continue
                totals = []
                for index in range(7):
                    values = [_amount(s[index].get("current_bet"), quantum) for s in old_slots]
                    totals.append(values[0] if values[0] == values[1] else None)
                earlier_folds = _earlier_street_folds(segment, old, new)
                accounted = list(totals)
                for index in earlier_folds:
                    if index != seat and accounted[index] is None:
                        accounted[index] = 0
                own = totals[seat]
                other = [
                    value
                    for index, value in enumerate(accounted)
                    if index != seat and value is not None
                ]
                if own is None or not other:
                    continue
                maximum = max(other)
                if maximum <= 0 or own <= maximum or increase != own - maximum:
                    continue
                opposing = [
                    index
                    for index, value in enumerate(accounted)
                    if index != seat and value == maximum
                ]
                if not all(_fold(s[index]) for s in new_slots for index in opposing):
                    continue
                if any(
                    s[seat].get("action_label") or s[seat].get("blind_label") for s in new_slots
                ):
                    continue
                unaccounted = [
                    i for i, value in enumerate(accounted) if i != seat and value is None
                ]
                all_folded = all(
                    i in earlier_folds or all(_fold(s[i]) for s in new_slots)
                    for i in range(7)
                    if i != seat
                )
                results.append(
                    dict(
                        hand_id=str(old[0]["context"]["hand_id"]["value"]),
                        seat=seat,
                        before=deepcopy(before),
                        after=deepcopy(after),
                        observed_stack_increase=increase,
                        repeated_visible_bets=totals,
                        accounted_street_bets=accounted,
                        earlier_street_fold_evidence=deepcopy(earlier_folds),
                        unknown_accounted_bet_seats=unaccounted,
                        all_opponents_fold_observed=all_folded,
                        opponent_coverage=(
                            "accounted_for" if not unaccounted and all_folded else "incomplete"
                        ),
                        repeated_pot_before=old_pots[0],
                        pot_after_observations=new_pots,
                        opposing_fold_seats=opposing,
                        unknown_other_bet_seats=[
                            index
                            for index, value in enumerate(totals)
                            if index != seat and value is None
                        ],
                        hypothesis="stack_increase_matches_visible_excess_after_fold",
                        candidate_return=increase,
                        returned_amount=None,
                        payout=None,
                        rake=None,
                        history_complete=False,
                        verified_for_training=False,
                        verified_for_statistics=False,
                        uses_later_evidence=True,
                        fold_evidence=[
                            {
                                "frame_id": r["frame_id"],
                                "captured_at": r["captured_at"],
                                "labels": [
                                    deepcopy(slots[index]["action_label"]) for index in opposing
                                ],
                            }
                            for r, slots in zip(new, new_slots, strict=True)
                        ],
                    )
                )
    return results
