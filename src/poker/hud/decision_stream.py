"""Offline request proposals. No model, transport, or execution of poker actions."""

import json
import math
import re
from copy import deepcopy
from datetime import datetime

from poker.hud.odds import validate

STREETS = {0: "preflop", 3: "flop", 4: "turn", 5: "river"}
AMOUNTS = ("total_pot", "call_amount_needed", "min_raise_amount", "max_raise_amount")
FLAGS = ("can_fold", "can_check", "can_call", "can_bet", "can_raise", "can_all_in")


def request_errors(payload):
    """Validate the proposed external contract, not the 330-float training format."""
    errors = []
    if payload.get("is_my_turn") is not True:
        errors.append("not_my_turn")
    try:
        validate(tuple(payload.get("hero_hole_cards", [])), tuple(payload.get("board_cards", [])))
    except (ValueError, TypeError):
        errors.append("cards_unknown_or_invalid")
    if payload.get("street_name") != STREETS.get(len(payload.get("board_cards", []))):
        errors.append("street_mismatch")
    for key in AMOUNTS:
        value = payload.get(key)
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            errors.append(key + "_unknown")
    for key in FLAGS:
        if type(payload.get(key)) is not bool:
            errors.append(key + "_unknown")
    players = payload.get("players", [])
    if not players:
        errors.append("players_unknown")
    seats = set()
    for player in players:
        seat = player.get("seat_index")
        if type(seat) is not int or seat < 0 or seat in seats:
            errors.append("invalid_seat")
        seats.add(seat)
        if not isinstance(player.get("name"), str):
            errors.append("invalid_name")
        for key in ("is_active", "is_dealer", "cards_dealt"):
            if type(player.get(key)) is not bool:
                errors.append("player_" + key + "_unknown")
        for key in ("stack", "current_bet"):
            value = player.get(key)
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                errors.append("player_" + key + "_unknown")
    if sum(p.get("is_dealer") is True for p in players) != 1:
        errors.append("dealer_unknown")

    # Known contradictions remain useful diagnostics even while other fields
    # are unknown. Never let a missing stack hide inconsistent action controls.
    def known_amount(key):
        value = payload.get(key)
        return type(value) in (int, float) and math.isfinite(value) and value >= 0

    if (
        known_amount("min_raise_amount")
        and known_amount("max_raise_amount")
        and payload["min_raise_amount"] > payload["max_raise_amount"]
    ):
        errors.append("invalid_raise_bounds")
    if all(payload.get(k) is False for k in FLAGS):
        errors.append("no_legal_actions")
    if (
        payload.get("can_check") is True
        and known_amount("call_amount_needed")
        and payload["call_amount_needed"] != 0
    ):
        errors.append("check_with_call_amount")
    if (
        payload.get("can_call") is True
        and known_amount("call_amount_needed")
        and payload["call_amount_needed"] == 0
    ):
        errors.append("call_without_amount")
    if payload.get("can_check") is True and payload.get("can_call") is True:
        errors.append("conflicting_check_call")
    if payload.get("can_bet") is True and payload.get("can_raise") is True:
        errors.append("conflicting_bet_raise")
    return sorted(set(errors))


def money(text):
    match = re.fullmatch(r"\s*(\d[\d ]*(?:[.,]\d{1,2})?)\s*(?:[pр₽]\.?)?\s*", text or "")
    return float(match[1].replace(" ", "").replace(",", ".")) if match else None


def blocker_comment(reasons):
    labels = {
        "table_membership_unverified": "состав и состояния игроков ещё не подтверждены",
        "betting_state_unverified": "ставки и доступные действия ещё не подтверждены",
        "awaiting_second_frame": "ожидается повторный кадр",
        "cards_not_confident": "карты прочитаны неуверенно",
        "cards_unknown_or_invalid": "не все карты распознаны",
        "hand_id_unknown": "номер раздачи не подтверждён",
        "newer_cards_disagree": "более свежий кадр показывает другие карты",
    }
    known = [labels[r] for r in reasons if r in labels]
    return "; ".join(known) or "см. список непроверенных полей в evidence.json"


def proposal(hand, seats, context=None):
    """Unknown facts remain null in drafts; they can never pass request_errors."""
    seats = list(seats)
    players = []
    for seat in sorted(seats, key=lambda s: s.key):
        players.append(
            {
                "seat_index": seat.key,
                "name": seat.name if not seat.conflict and not seat.missing else "",
                "is_active": None,
                "is_dealer": None,
                "stack": money(seat.observation.stack) if not seat.missing else None,
                "current_bet": None,
                "cards_dealt": None,
            }
        )
    result = {
        "is_my_turn": hand.my_turn,
        "street_name": STREETS.get(len(hand.board)),
        "board_cards": list(hand.board),
        "hero_hole_cards": list(hand.hero),
        **dict.fromkeys(AMOUNTS),
        "players": players,
        **dict.fromkeys(FLAGS),
    }
    words = (context or {}).get("regions", {}).get("table_text", {}).get("words", [])
    for i, word in enumerate(words[:-1]):
        if word["text"].casefold().rstrip(":") in {"bank", "банк"}:
            following = words[i + 1]
            if word.get("confidence", 0) >= 65 and following.get("confidence", 0) >= 85:
                result["total_pot"] = money(following["text"])
            break
    signals = (context or {}).get("table_signals", {})
    if signals.get("slots"):
        players = []
        for slot in signals["slots"]:
            x, y, w, h = slot["roi"]
            nearby = [
                s
                for s in seats
                if not s.missing and math.dist(s.observation.roi[:2], (x, y)) < w * 0.6
            ]
            seat = min(nearby, key=lambda s: math.dist(s.observation.roi[:2], (x, y)), default=None)
            players.append(
                {
                    "seat_index": slot["seat_index"],
                    "name": seat.name if seat and not seat.conflict else "",
                    "is_active": False
                    if (slot.get("action_label") or {}).get("action") == "fold"
                    else None,
                    "is_dealer": slot.get("is_dealer"),
                    "stack": money(seat.observation.stack) if seat else None,
                    "current_bet": slot.get("current_bet"),
                    "cards_dealt": None,
                }
            )
        result["players"] = players
    if "pot" in signals:
        # Do not bypass a dedicated reader's rejection with a looser regional
        # word match (which may omit currency or contain conflicting amounts).
        result["total_pot"] = signals["pot"].get("value")
    control = signals.get("controls", {})
    result.update(control.get("flags", {}))
    if control.get("call_amount") is not None:
        result["call_amount_needed"] = control["call_amount"]
    return result


class DecisionStream:
    """Two matching fresh observations, deduplication within a turn, explicit blockers."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.key = None
        self.count = 0
        self.last_frame = None
        self.emitted = None
        self.last_captured = None

    def update(self, payload, metadata, hand_id, *, cards_valid, blockers=(), now=None):
        if payload.get("is_my_turn") is not True:
            self.reset()
            return None
        captured = datetime.fromisoformat(metadata["captured_at"])
        now = now or datetime.now(captured.tzinfo)
        age = (now - captured).total_seconds()
        if not 0 <= age <= 5:
            self.reset()
            return None
        # Names are identity metadata; an OCR spelling fluctuation must not create a turn.
        stable = {
            **payload,
            "players": [{k: v for k, v in p.items() if k != "name"} for p in payload["players"]],
        }
        key = (
            metadata.get("window"),
            tuple(metadata.get("client_rect", [])),
            hand_id,
            metadata.get("evidence_epoch"),
            metadata.get("hero_seat"),
            json.dumps(stable, sort_keys=True),
        )
        frame = metadata["frame_id"]
        if self.last_captured and captured <= self.last_captured:
            return None
        if self.last_frame is not None and frame == self.last_frame:
            return None
        if self.last_captured and (captured - self.last_captured).total_seconds() > 5:
            self.count = 0
        self.last_captured = captured
        if key != self.key:
            self.key, self.count = key, 0
        if frame != self.last_frame:
            # Identical card strings with low recognition confidence are not
            # independent confirmations of a reliable decision state.
            self.count = self.count + 1 if cards_valid else 0
            self.last_frame = frame
        reasons = request_errors(payload) + list(blockers)
        if not cards_valid:
            reasons.append("cards_not_confident")
        if not re.fullmatch(r"\d{8,14}", hand_id or ""):
            reasons.append("hand_id_unknown")
        if self.count < 2:
            reasons.append("awaiting_second_frame")
        reasons = sorted(set(reasons))
        signature = (key, tuple(reasons))
        if signature == self.emitted:
            return None
        self.emitted = signature
        return {
            "contract_version": 1,
            "mode": "dry_run",
            "would_send": not reasons,
            "blockers": reasons,
            "request": deepcopy(payload),
            "hand_id": hand_id,
            "confirmations": self.count,
            "source": deepcopy(metadata),
        }
