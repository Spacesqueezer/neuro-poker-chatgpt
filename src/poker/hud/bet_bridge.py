"""Join confirmed fast facts to a current frame, never future observations."""

from collections import deque
from copy import deepcopy
from datetime import datetime
from types import SimpleNamespace

from poker.hud.decision_stream import STREETS
from poker.hud.raise_cap import confirmed_raise_cap, refresh_round_trip_cap
from poker.hud.raise_minimum import bridge_minimum
from poker.hud.seat_evidence import confirmed_bets


class BetBridge:
    def __init__(self):
        self.rows = deque(maxlen=32)
        self.confirmed_caps = deque(maxlen=8)

    def add(self, metadata, context, evidence):
        self.rows.append(deepcopy({**metadata, "context": context, "evidence": evidence}))

    def augment(self, metadata, context, evidence):
        at = datetime.fromisoformat(metadata["captured_at"])
        candidates = [
            row
            for row in self.rows
            if row.get("evidence_epoch") == metadata.get("evidence_epoch")
            and row["context"].get("hero_seat", 6) == context.get("hero_seat", 6)
            and datetime.fromisoformat(row["captured_at"]) <= at
        ]
        if not candidates:
            return evidence
        duplicates = [r for r in candidates if r["frame_id"] == metadata["frame_id"]]
        if duplicates:
            if any(not self._same_capture_agrees(metadata, context, r) for r in duplicates):
                return evidence
            candidates = [
                r
                for r in candidates
                if r["frame_id"] != metadata["frame_id"]
                and datetime.fromisoformat(r["captured_at"]) < at
            ]
            if not candidates:
                return evidence
        previous = max(candidates, key=lambda row: row["captured_at"])
        if (at - datetime.fromisoformat(previous["captured_at"])).total_seconds() > 2:
            return evidence
        hand_id = evidence.get("hand_id")
        if not hand_id or previous["evidence"].get("hand_id") != hand_id:
            return evidence
        row = {**metadata, "context": context}
        row["client_rect"] = list(row["client_rect"])
        previous = {**previous, "client_rect": list(previous["client_rect"])}
        tracker = SimpleNamespace(
            current={"hand_id": hand_id},
            source=row,
            street=STREETS.get(len(context.get("decision_hand", {}).get("board", []))),
        )
        matches = confirmed_bets(row, previous, tracker)
        result = deepcopy(evidence)
        for seat, match in matches.items():
            prior = previous["evidence"]["bet_confirmations"].get(seat)
            if not prior or prior["value"] != match["value"] or prior["street"] != match["street"]:
                continue
            if seat in result["bet_confirmations"]:
                continue
            result["bet_confirmations"][seat] = {
                **match,
                "confirmation_frames": deepcopy(prior["confirmation_frames"])
                + [match["confirmation_frames"][-1]],
                "method": "fast_pair_plus_current_text_frame"
                if context.get("observation_source") != "fast_table"
                else "fast_pair_plus_current_frame",
            }
        self._participation(row, previous, result)
        cap = confirmed_raise_cap(row, previous, result)
        if cap is not None:
            result["max_raise_confirmation"] = cap
            self.confirmed_caps.append(deepcopy({**row, "max_raise_confirmation": cap}))
        minimum = bridge_minimum(row, previous)
        if minimum is not None:
            result["min_raise_confirmation"] = minimum
        if result.get("min_raise_confirmation") and cap is None:
            for old in reversed(self.confirmed_caps):
                refreshed = refresh_round_trip_cap(row, old, result)
                if refreshed is not None:
                    result["max_raise_confirmation"] = refreshed
                    break
        return result

    @staticmethod
    def _same_capture_agrees(metadata, context, fast):
        """A duplicate capture is not independent evidence or a reason to hide conflicts."""
        if (
            metadata["captured_at"] != fast["captured_at"]
            or metadata.get("window") != fast.get("window")
            or tuple(metadata.get("client_rect", [])) != tuple(fast.get("client_rect", []))
        ):
            return False
        old = fast["context"]
        if any(c.get("hand_id", {}).get("confidence", 0) < 80 for c in (context, old)):
            return False
        if context.get("hand_id", {}).get("value") != old.get("hand_id", {}).get("value"):
            return False
        for key in ("hero", "board", "valid"):
            if context.get("decision_hand", {}).get(key) != old.get("decision_hand", {}).get(key):
                return False
        slots = [c.get("table_signals", {}).get("slots", []) for c in (context, old)]
        if any([s.get("seat_index") for s in items] != list(range(7)) for items in slots):
            return False
        for a, b in zip(*slots, strict=True):
            if any(a.get(k) != b.get(k) for k in ("roi", "current_bet", "settlement_label")):
                return False
            for key, field in (
                ("bet_evidence", "value"),
                ("action_label", "action"),
                ("card_back_evidence", "present"),
            ):
                if (a.get(key) or {}).get(field) != (b.get(key) or {}).get(field):
                    return False
        return True

    @staticmethod
    def _participation(row, previous, result):
        current_context, old_context = row["context"], previous["context"]
        current_hand = current_context.get("decision_hand", {})
        old_hand = old_context.get("decision_hand", {})
        if (
            row["frame_id"] == previous["frame_id"]
            or row["captured_at"] <= previous["captured_at"]
            or any(row.get(k) != previous.get(k) for k in ("window", "client_rect"))
            or not current_hand.get("valid")
            or not old_hand.get("valid")
            or current_hand.get("board") != old_hand.get("board")
            or current_hand.get("hero") != old_hand.get("hero")
            or any(
                c.get("hand_id", {}).get("value") != result["hand_id"]
                or c.get("hand_id", {}).get("confidence", 0) < 80
                for c in (current_context, old_context)
            )
        ):
            return
        slots = current_context.get("table_signals", {}).get("slots", [])
        old_slots = old_context.get("table_signals", {}).get("slots", [])
        if any(
            [s.get("seat_index") for s in items] != list(range(7)) for items in (slots, old_slots)
        ):
            return
        for slot, old_slot in zip(slots, old_slots, strict=True):
            seat = slot["seat_index"]
            if (
                seat in result.get("participation_evidence", {})
                or str(seat) in result.get("hand_participants", [])
                or slot["roi"] != old_slot["roi"]
                or slot.get("settlement_label")
                or (slot.get("action_label") or {}).get("action") == "fold"
            ):
                continue
            prior = previous["evidence"].get("participation_evidence", {}).get(seat, {})
            if prior.get("cards_dealt") is not True or prior.get("is_active") is not True:
                continue
            visible = slot.get("card_back_evidence", {}).get("present") is True
            if seat == current_context.get("hero_seat", 6):
                visible = len(current_hand.get("hero", [])) == 2
            if not visible:
                continue
            result.setdefault("participation_evidence", {})[seat] = {
                **deepcopy(prior),
                "method": "fast_participation_plus_current_cards",
                "current_frame": {
                    **{k: row[k] for k in ("frame_id", "captured_at", "image")},
                    "card_back_evidence": deepcopy(slot.get("card_back_evidence")),
                    "hero_cards": current_hand.get("hero")
                    if seat == current_context.get("hero_seat", 6)
                    else None,
                },
            }
            result.setdefault("hand_participants", []).append(str(seat))
            result.get("empty_seat_confirmations", {}).pop(seat, None)
