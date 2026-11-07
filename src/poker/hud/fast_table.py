"""Frame-local decision facts and action monitoring, independent of nickname OCR."""

import time
from concurrent.futures import ThreadPoolExecutor

from poker.hud.card_backs import card_back_pair
from poker.hud.cards import find_cards
from poker.hud.client_id import read_hand_id
from poker.hud.context import dealer_candidates, read_slot_stack
from poker.hud.hand import observe
from poker.hud.pipeline import my_turn
from poker.hud.recognition import layout_panels
from poker.hud.seat_occupancy import read_empty_seat
from poker.hud.slider import field_and_knob
from poker.hud.table_signals import (
    anchored_pot,
    controls,
    locate_dealer,
    read_action_label,
    read_bet,
    read_settlement_label,
)


def decision_fields(frame, rois):
    started = time.monotonic()
    signals, errors = {}, []
    for key, reader in (
        ("controls", lambda: controls(frame)),
        ("slider_evidence", lambda: field_and_knob(frame)),
        ("pot", lambda: anchored_pot(frame)),
        ("dealer_slot", lambda: locate_dealer(rois, dealer_candidates(frame))),
    ):
        try:
            signals[key] = reader()
        except Exception as error:
            errors.append(f"{key}: {error}")
    signals.setdefault("pot", {"value": None})
    signals.setdefault("dealer_slot", None)
    return signals, errors, (time.monotonic() - started) * 1000


def seat_fields(frame, roi, index, hero_turn):
    started = time.monotonic()
    bet = read_bet(frame, roi, index)
    settlement = read_settlement_label(frame, roi)
    slot = {
        "seat_index": index,
        "roi": list(roi),
        "current_bet": None if settlement else bet["value"],
        "bet_evidence": bet,
        "settlement_label": settlement,
        "action_label": read_action_label(frame, roi),
        "card_back_evidence": card_back_pair(frame, roi),
    }
    stack, empty, errors = None, None, []
    # Current amounts are read on this exact decision frame, never copied from
    # a previous name result. Off-turn action monitoring stays lightweight.
    if hero_turn:
        try:
            stack = read_slot_stack(frame, slot)
        except Exception as error:
            stack = {"value": None, "error": str(error)}
            errors.append(f"stack_{index}: {error}")
        try:
            empty = read_empty_seat(frame, roi)
        except Exception as error:
            empty = {"empty": None, "error": str(error)}
            errors.append(f"empty_seat_{index}: {error}")
    return slot, stack, empty, errors, (time.monotonic() - started) * 1000


def analyze_fast_table(frame, hero_seat=6):
    started = time.monotonic()
    rois = layout_panels(frame)
    if len(rois) != 7:
        return {"table_signals": {"slots": []}, "errors": ["layout_unknown"]}
    identity = read_hand_id(frame)
    hand = observe(
        (find_cards(frame) if hero_seat == 6 else find_cards(frame, hero_seat=hero_seat)),
        my_turn(frame),
    )
    identity_ms = (time.monotonic() - started) * 1000
    # At most three concurrent OCR calls here. All readers see the same immutable
    # frame; assembling futures in physical-seat order preserves deterministic output.
    with ThreadPoolExecutor(max_workers=3, thread_name_prefix="hud-decision") as pool:
        header = pool.submit(decision_fields, frame, rois) if hand.my_turn else None
        pending = [
            pool.submit(seat_fields, frame, roi, i, hand.my_turn) for i, roi in enumerate(rois)
        ]
        signals, errors, header_ms = header.result() if header else ({}, [], 0.0)
        rows = [future.result() for future in pending]
    slots, stacks, empty, seat_ms = [], {}, {}, []
    for slot, stack, vacant, problems, elapsed in rows:
        seat = slot["seat_index"]
        if "dealer_slot" in signals:
            dealer = signals["dealer_slot"]
            slot["is_dealer"] = seat == dealer if dealer is not None else None
        slots.append(slot)
        if stack is not None:
            stacks[seat] = stack
        if vacant is not None:
            empty[seat] = vacant
        errors.extend(problems)
        seat_ms.append(round(elapsed, 1))
    signals["slots"] = slots
    return {
        "observation_source": "fast_table",
        "hand_id": identity,
        "decision_hand": hand.to_dict(),
        "hero_seat": hero_seat,
        "hero_visible": len(hand.hero) == 2,
        "table_signals": signals,
        "stack_readings": stacks,
        "empty_seat_readings": empty,
        "errors": errors,
        "stage_ms": {
            "identity_and_cards": round(identity_ms, 1),
            "decision_fields": round(header_ms, 1),
            "seats": seat_ms,
        },
        "total_ms": round((time.monotonic() - started) * 1000, 1),
    }
