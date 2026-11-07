"""Confirm a visible minimum only after a bounded left/right/left round trip."""

import math
from copy import deepcopy
from datetime import datetime


def observation(row):
    context = row["context"]
    hand = context.get("decision_hand", {})
    identity = context.get("hand_id", {})
    signals = context.get("table_signals", {})
    controls = signals.get("controls", {})
    slider = signals.get("slider_evidence", {})
    selected = controls.get("selected_wager") or {}
    value = (slider.get("field") or {}).get("value")
    call = controls.get("call_amount")
    action = selected.get("action")
    endpoint = slider.get("endpoint")
    if (
        not hand.get("valid")
        or not hand.get("my_turn")
        or identity.get("confidence", 0) < 80
        or not identity.get("value")
        or not row.get("window")
        or len(row.get("client_rect", [])) != 4
        or type(value) not in (int, float)
        or not math.isfinite(value)
        or value <= 0
        or type(call) not in (int, float)
        or not math.isfinite(call)
        or call < 0
        or selected.get("value") != value
        or action not in ("bet", "raise", "all_in")
        or controls.get("flags", {}).get("can_" + action) is not True
        or endpoint not in ("left", "right", "interior")
        or (endpoint == "right" and action != "all_in")
        or (endpoint == "left" and action not in ("bet", "raise"))
    ):
        return None
    key = (
        identity["value"],
        row["window"],
        tuple(row["client_rect"]),
        row.get("evidence_epoch"),
        tuple(hand.get("hero", [])),
        tuple(hand.get("board", [])),
        call,
    )
    return key, endpoint, value, action


class MinimumRoundTrip:
    """No persistence across missing controls, changed context, or long capture gaps."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.key = self.last = self.left = self.right = None

    def update(self, row, endpoint):
        current = observation(row)
        if current is None:
            self.reset()
            return None
        key, side, value, action = current
        at = datetime.fromisoformat(row["captured_at"])
        if self.key != key or (self.last and not 0 < (at - self.last).total_seconds() <= 5):
            self.reset()
        self.key, self.last = key, at
        if self.left and (at - self.left[0]).total_seconds() > 30:
            self.left = self.right = None
        if self.left and side == "left" and (value, action) != self.left[1:3]:
            self.left = self.right = None
        if not endpoint:
            return None
        sources = endpoint["confirmation_frames"]
        if side == "left":
            if self.left and self.right:
                return {
                    "value": value,
                    "semantics": "street_total_including_current_bet",
                    "method": "confirmed_left_right_left_round_trip",
                    "initial_left": deepcopy(self.left[3]),
                    "right_endpoint": deepcopy(self.right),
                    "confirmation_frames": deepcopy(sources),
                    "selected_action": action,
                }
            self.left = (
                datetime.fromisoformat(sources[0]["captured_at"]),
                value,
                action,
                deepcopy(sources),
            )
        elif side == "right" and self.left:
            if value <= self.left[1]:
                self.left = self.right = None
            else:
                self.right = {"value": value, "confirmation_frames": deepcopy(sources)}
        return None


def bridge_minimum(row, previous):
    """Require a fresh third left reading before transferring the fast-stream proof."""
    proof = previous.get("evidence", {}).get("min_raise_confirmation")
    current, old = observation(row), observation(previous)
    if not proof or current is None or current != old or current[1] != "left":
        return None
    at = datetime.fromisoformat(row["captured_at"])
    age = (at - datetime.fromisoformat(previous["captured_at"])).total_seconds()
    if not 0 < age <= 2 or proof["value"] != current[2]:
        return None
    if any(
        not 0 < (at - datetime.fromisoformat(s["captured_at"])).total_seconds() <= 30
        for s in proof["initial_left"]
    ):
        return None
    sources = proof["confirmation_frames"]
    if row["frame_id"] in {s["frame_id"] for s in sources}:
        return None
    result = deepcopy(proof)
    result["confirmation_frames"].append(
        {k: row.get(k) for k in ("frame_id", "captured_at", "image")}
    )
    result["method"] += "_plus_current_text_frame"
    return result
