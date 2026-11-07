"""Confirm a visible all-in street total without deriving a minimum raise."""

import math
from copy import deepcopy
from datetime import datetime

from poker.hud.raise_minimum import observation


def refresh_round_trip_cap(row, previous, facts):
    """Reuse an observed cap only inside its completed cycle with fresh hero amounts."""
    hero = row["context"].get("hero_seat", 6)
    if (
        type(hero) is not int
        or not 0 <= hero <= 6
        or previous["context"].get("hero_seat", 6) != hero
    ):
        return None
    minimum = facts.get("min_raise_confirmation")
    cap = previous.get("max_raise_confirmation")
    current, old = observation(row), observation(previous)
    if not minimum or not cap or current is None or old is None:
        return None
    if current[0] != old[0] or current[1] != "left" or old[1] != "right":
        return None
    right = minimum["right_endpoint"]
    if cap["value"] != right["value"] or minimum["value"] >= cap["value"]:
        return None
    # The cap must belong to this actual right-endpoint visit, not another visit
    # that happened to show the same amount during this hand.
    if not (
        {s["frame_id"] for s in right["confirmation_frames"]}
        & {s["frame_id"] for s in cap["confirmation_frames"]}
    ):
        return None
    at = datetime.fromisoformat(row["captured_at"])
    if not 0 < (at - datetime.fromisoformat(previous["captured_at"])).total_seconds() <= 30:
        return None
    amounts = []
    for key, cap_key in (
        ("stack_confirmations", "hero_stack"),
        ("bet_confirmations", "hero_current_bet"),
    ):
        fact = facts.get(key, {}).get(hero, {})
        amount = fact.get("value")
        sources = fact.get("confirmation_frames", [])
        if (
            amount != cap[cap_key]["value"]
            or type(amount) not in (int, float)
            or not math.isfinite(amount)
            or amount < 0
            or len(sources) < 2
            or len({s["frame_id"] for s in sources}) != len(sources)
            or sources[-1]["frame_id"] != row["frame_id"]
            or any(
                not 0 <= (at - datetime.fromisoformat(s["captured_at"])).total_seconds() <= 5
                for s in sources
            )
        ):
            return None
        amounts.append(amount)
    if round(sum(amounts), 2) != cap["value"]:
        return None
    return {
        **deepcopy(cap),
        "method": "observed_cap_rechecked_after_confirmed_round_trip",
        "revalidated_at": {k: row.get(k) for k in ("frame_id", "captured_at", "image")},
        "hero_stack": deepcopy(facts["stack_confirmations"][hero]),
        "hero_current_bet": deepcopy(facts["bet_confirmations"][hero]),
    }


def confirmed_raise_cap(row, previous, facts):
    contexts = (row["context"], previous["context"])
    hero = contexts[0].get("hero_seat", 6)
    if type(hero) is not int or not 0 <= hero <= 6 or contexts[1].get("hero_seat", 6) != hero:
        return None
    endpoint = previous.get("evidence", {}).get("slider_endpoint") or {}
    value = endpoint.get("value")
    if (
        endpoint.get("endpoint") != "right"
        or type(value) not in (int, float)
        or not math.isfinite(value)
    ):
        return None
    if value <= 0 or endpoint.get("hand_id") != facts.get("hand_id"):
        return None
    if any(row.get(k) != previous.get(k) for k in ("window", "client_rect", "evidence_epoch")):
        return None
    now = datetime.fromisoformat(row["captured_at"])
    age = (now - datetime.fromisoformat(previous["captured_at"])).total_seconds()
    if not 0 < age <= 2 or row["frame_id"] == previous["frame_id"]:
        return None
    for context in contexts:
        hand = context.get("decision_hand", {})
        identity = context.get("hand_id", {})
        signals = context.get("table_signals", {})
        control = signals.get("controls", {})
        selected = control.get("selected_wager") or {}
        slider = signals.get("slider_evidence", {})
        if (
            not hand.get("valid")
            or not hand.get("my_turn")
            or identity.get("value") != facts.get("hand_id")
            or identity.get("confidence", 0) < 80
            or [s.get("seat_index") for s in signals.get("slots", [])] != list(range(7))
            or selected.get("action") != "all_in"
            or selected.get("value") != value
            or control.get("flags", {}).get("can_all_in") is not True
            or slider.get("endpoint") != "right"
            or (slider.get("field") or {}).get("value") != value
            or control.get("call_amount") is None
        ):
            return None
    if any(
        contexts[0]["decision_hand"].get(k) != contexts[1]["decision_hand"].get(k)
        for k in ("hero", "board")
    ):
        return None
    if contexts[0]["table_signals"]["slots"][hero].get("roi") != contexts[1]["table_signals"][
        "slots"
    ][hero].get("roi"):
        return None
    if (
        contexts[0]["table_signals"]["controls"]["call_amount"]
        != contexts[1]["table_signals"]["controls"]["call_amount"]
    ):
        return None
    sources = endpoint.get("confirmation_frames", [])
    if len(sources) != 2 or len({s["frame_id"] for s in sources} | {row["frame_id"]}) != 3:
        return None
    if any(
        not 0 < (now - datetime.fromisoformat(s["captured_at"])).total_seconds() <= 5
        for s in sources
    ):
        return None
    amounts = []
    for key in ("stack_confirmations", "bet_confirmations"):
        fact = facts.get(key, {}).get(hero, {})
        amount = fact.get("value")
        confirms = fact.get("confirmation_frames", [])
        if (
            type(amount) not in (int, float)
            or not math.isfinite(amount)
            or amount < 0
            or len(confirms) < 2
            or len({s["frame_id"] for s in confirms}) != len(confirms)
            or confirms[-1]["frame_id"] != row["frame_id"]
            or any(
                not 0 <= (now - datetime.fromisoformat(s["captured_at"])).total_seconds() <= 5
                for s in confirms
            )
        ):
            return None
        amounts.append(amount)
    if round(sum(amounts), 2) != value:
        return None
    return {
        "value": value,
        "semantics": "street_total_including_current_bet",
        "method": "right_endpoint_all_in_plus_confirmed_stack_and_bet",
        "confirmation_frames": deepcopy(sources)
        + [{k: row.get(k) for k in ("frame_id", "captured_at", "image")}],
        "hero_stack": deepcopy(facts["stack_confirmations"][hero]),
        "hero_current_bet": deepcopy(facts["bet_confirmations"][hero]),
    }
