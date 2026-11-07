"""Bounded live confirmation of observed facts; no OCR, model or database writes."""

from copy import deepcopy
from datetime import datetime

from poker.hud.hand_reconstruction import HandReconstructor
from poker.hud.raise_minimum import MinimumRoundTrip
from poker.hud.seat_evidence import ConfirmedStacks, confirmed_bets, participation
from poker.hud.seat_occupancy import EmptySeatTracker, filter_empty_players
from poker.hud.slider import EndpointConfirmation
from poker.hud.title_stakes import TitleStakesConfirmation


class LiveEvidence:
    def __init__(self):
        self.epoch = 0
        self.reset()

    def reset(self):
        self.epoch += 1
        self.tracker = HandReconstructor()
        self.stacks = ConfirmedStacks()
        self.empty_seats = EmptySeatTracker()
        self.slider = EndpointConfirmation()
        self.minimum = MinimumRoundTrip()
        self.title_stakes = TitleStakesConfirmation()
        self.previous = None

    def update(self, context, metadata, players=(), *, now=None):
        if metadata.get("evidence_epoch") != self.epoch:
            return None
        at = datetime.fromisoformat(metadata["captured_at"])
        if self.previous and self.previous["context"].get("hero_seat", 6) != context.get(
            "hero_seat", 6
        ):
            self.reset()
            return None
        now = now or datetime.now(at.tzinfo)
        if not 0 <= (now - at).total_seconds() <= 5:
            self.reset()
            return None
        if self.previous and (
            at <= datetime.fromisoformat(self.previous["captured_at"])
            or metadata["frame_id"] == self.previous["frame_id"]
        ):
            return None
        row = {**metadata, "context": context, "players": list(players)}
        row.setdefault("image", None)
        signals = context.get("table_signals", {})
        endpoint = self.slider.update(
            {
                **metadata,
                "image": row["image"],
                "controls": signals.get("controls", {}),
                "board_cards": context.get("decision_hand", {}).get("board", []),
            },
            context.get("hand_id", {}),
            signals.get("slider_evidence", {}),
        )
        self.tracker.update(row)
        bets = confirmed_bets(row, self.previous, self.tracker)
        participants = participation(self.tracker)
        readings = {int(k): v for k, v in context.get("stack_readings", {}).items()}
        stacks = self.stacks.update(row, readings)
        slots = context.get("table_signals", {}).get("slots", [])
        occupied = {
            s["seat_index"]
            for s in slots
            if s.get("card_back_evidence", {}).get("present") is True
            or s.get("current_bet") is not None
            or s.get("action_label")
            or s.get("is_dealer") is True
        }
        occupied.update(k for k, reading in readings.items() if reading.get("value") is not None)
        occupied.update(participants)
        empty = self.empty_seats.update(
            row, {int(k): v for k, v in context.get("empty_seat_readings", {}).items()}, occupied
        )
        self.previous = row
        hand = self.tracker.current
        # Keep only this hand; full history belongs in the recorder, not RAM.
        self.tracker.hands = {hand["hand_id"]: hand} if hand else {}
        return deepcopy(
            {
                "schema_version": 1,
                "hand_id": hand["hand_id"] if hand else None,
                "table_stakes": self.title_stakes.update(metadata, context.get("hand_id", {})),
                "participation_evidence": participants,
                "bet_confirmations": bets,
                "stack_confirmations": stacks,
                "empty_seat_confirmations": empty,
                "slider_endpoint": endpoint,
                "min_raise_confirmation": self.minimum.update(row, endpoint) or {},
                "hand_participants": list(hand["participants"]) if hand else [],
                "history_complete": False,
                "model_called": False,
            }
        )

    @staticmethod
    def apply(payload, facts):
        """Never let raw single-frame amounts masquerade as confirmed facts."""
        payload = {
            **payload,
            "min_raise_amount": facts.get("min_raise_confirmation", {}).get("value"),
            "max_raise_amount": facts.get("max_raise_confirmation", {}).get("value"),
        }
        payload, _ = filter_empty_players(
            payload,
            facts.get("empty_seat_confirmations", {}),
            {"participants": dict.fromkeys(facts.get("hand_participants", []))}
            if facts.get("hand_id")
            else None,
        )
        for player in payload["players"]:
            seat = player["seat_index"]
            participant = facts["participation_evidence"].get(seat, {})
            player["cards_dealt"] = participant.get("cards_dealt")
            player["is_active"] = participant.get("is_active")
            player["current_bet"] = facts["bet_confirmations"].get(seat, {}).get("value")
            player["stack"] = facts.get("stack_confirmations", {}).get(seat, {}).get("value")
        return payload
