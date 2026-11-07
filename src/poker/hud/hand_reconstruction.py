"""Reconstruct observed hand fragments. Never manufacture a complete betting history."""

import math
import re
from datetime import datetime

STREETS = {0: "preflop", 3: "flop", 4: "turn", 5: "river"}
ACTIONS = {"fold", "check", "call", "bet", "raise", "all_in"}


class HandReconstructor:
    def __init__(self):
        self.hands = {}
        self.last = None
        self.identity = None
        self.identity_count = 0
        self.current = None
        self.skipped = 0
        self.break_continuity()

    def break_continuity(self, reason=None):
        if reason and self.current:
            self.current["warnings"] = sorted(set(self.current["warnings"] + [reason]))
        self.amounts = {}
        self.amount_times = {}
        self.baselines = {}
        self.labels = {}
        self.recent_labels = {}
        self.action_epoch = 0
        self.blinds = {}
        self.dealer = (None, [])
        self.presence = {}
        self.street_candidate = None
        self.street_count = 0
        self.street = None
        self.street_sources = []
        self.confirmed_street = None
        self.street_source = None

    def interrupt(self, reason):
        self.break_continuity(reason)
        self.identity, self.identity_count, self.current = None, 0, None

    def update(self, row):
        context = row.get("context", {})
        frame_id = row.get("frame_id")
        try:
            at = datetime.fromisoformat(row["captured_at"])
        except (KeyError, TypeError, ValueError):
            self.skipped += 1
            self.interrupt("invalid_capture_time")
            return
        boundary = (row.get("window"), tuple(row.get("client_rect", [])))
        if self.last:
            old_at, old_frame, old_boundary = self.last
            if at <= old_at or frame_id == old_frame:
                self.skipped += 1
                return
            if boundary != old_boundary or (at - old_at).total_seconds() > 10:
                self.interrupt("gap_in_observations")
        self.last = at, frame_id, boundary
        identity = context.get("hand_id", {})
        key = identity.get("value", "")
        if not re.fullmatch(r"\d{8,14}", str(key)) or identity.get("confidence", 0) < 80:
            self.skipped += 1
            self.interrupt("hand_id_unknown")
            return
        if key != self.identity:
            self.break_continuity()
            self.identity, self.identity_count, self.current = key, 1, None
            self.identity_source = {"frame_id": frame_id, "captured_at": row["captured_at"]}
            self.skipped += 1
            return
        self.identity_count += 1
        self.current = self.hands.setdefault(
            key,
            {
                "schema_version": 1,
                "hand_id": key,
                "window": row.get("window"),
                "first_at": row["captured_at"],
                "last_at": row["captured_at"],
                "participants": {},
                "events": [],
                "warnings": [],
                "history_complete": False,
                "verified_for_statistics": False,
                "identity_frames": [
                    self.identity_source,
                    {"frame_id": frame_id, "captured_at": row["captured_at"]},
                ],
            },
        )
        hand = self.current
        hand["last_at"] = row["captured_at"]
        self.source = {
            "frame_id": frame_id,
            "captured_at": row["captured_at"],
            "image": row.get("image"),
        }
        if "evidence_epoch" in row:
            self.source["evidence_epoch"] = row["evidence_epoch"]
        signals = context.get("table_signals", {})
        slots = signals.get("slots", [])
        if [s.get("seat_index") for s in slots] != list(range(7)):
            self.skipped += 1
            self.break_continuity("layout_unknown")
            return
        if "dealer_slot" in signals:
            dealer = signals["dealer_slot"]
            old_dealer, sources = self.dealer
            if type(dealer) is int and 0 <= dealer < 7:
                fresh = (
                    sources
                    and (at - datetime.fromisoformat(sources[-1]["captured_at"])).total_seconds()
                    <= 10
                )
                sources = (sources[-1:] if old_dealer == dealer and fresh else []) + [self.source]
                self.dealer = dealer, sources
                existing = [e for e in hand["events"] if e["kind"] == "dealer_observed"]
                if len(sources) == 2 and not any(e["seat_index"] == dealer for e in existing):
                    if existing:
                        hand["warnings"] = sorted(set(hand["warnings"] + ["dealer_conflict"]))
                    self.emit("dealer_observed", seat_index=dealer, confirmation_frames=sources)
            else:
                self.dealer = (None, [])
        board = list(context.get("decision_hand", {}).get("board", []))
        valid_board = (
            len(board) in STREETS
            and len(set(board)) == len(board)
            and all(re.fullmatch(r"[2-9TJQKA][shdc]", c) for c in board)
        )
        proposed = STREETS[len(board)] if valid_board else None
        known_board = hand.get("board_cards", [])
        if valid_board and (
            len(board) < len(known_board) or board[: len(known_board)] != known_board
        ):
            hand["warnings"] = sorted(set(hand["warnings"] + ["board_conflict"]))
            proposed = None
        if proposed == "preflop" and not (
            context.get("hero_visible")
            or any(
                s.get("card_back_evidence", {}).get("present") is True
                for s in signals.get("slots", [])
            )
        ):
            proposed = None
        candidate = (proposed, tuple(board)) if proposed is not None else None
        if candidate != self.street_candidate:
            self.street_candidate, self.street_count = candidate, 1
            self.street_sources = [self.source] if candidate else []
        else:
            self.street_count += 1
            self.street_sources = (self.street_sources[-1:] + [self.source]) if candidate else []
        if proposed != self.street:
            self.amounts.clear()
            self.baselines.clear()
            if proposed is None or self.street_count < 2:
                self.street = None
            else:
                self.street = proposed
                hand["board_cards"] = list(board)
                self.emit(
                    "street_observed",
                    street=proposed,
                    board_cards=list(board),
                    confirmation_frames=list(self.street_sources),
                    previous_street=self.confirmed_street,
                    previous_street_source=self.street_source,
                    previous_street_final_verified=False,
                )
                first, second = self.street_sources
                if (at - datetime.fromisoformat(first["captured_at"])).total_seconds() <= 5:
                    for event in hand["events"]:
                        if (
                            event["kind"] == "action_label"
                            and event.get("street") is None
                            and event["frame_id"] == first["frame_id"]
                            and event["captured_at"] == first["captured_at"]
                            and event.get("street_candidate")
                            == {"street": proposed, "board_cards": board}
                        ):
                            # The earlier event stays unknown until this second
                            # capture arrives. Keep the later evidence explicit.
                            event["street"] = proposed
                            event["street_confirmation_frames"] = [first, second]
        if self.street is not None:
            self.confirmed_street = self.street
            self.street_source = self.source
        action_street = self.street
        partial_river = (
            action_street is None
            and self.confirmed_street == "river"
            and len(board) == len(known_board) == 5
            and board.count("") == 1
            and all(
                not card or card == known for card, known in zip(board, known_board, strict=True)
            )
            and self.street_source is not None
            and (at - datetime.fromisoformat(self.street_source["captured_at"])).total_seconds()
            <= 5
        )
        if partial_river:
            # Five positions still visible, four agreeing cards and a fresh
            # confirmed river establish the street, not the missing card value.
            action_street = "river"
        present = set()
        labels = dict(self.labels)
        for slot in slots:
            seat = slot["seat_index"]
            present.add(seat)
            label = slot.get("action_label") or {}
            action = label.get("action")
            sampled_action = slot.get("action_sampled", True)
            if not sampled_action:
                action = None
            words = label.get("words", [])
            if action not in ACTIONS or not words or min(w["confidence"] for w in words) < 85:
                action = None
            pair = slot.get("card_back_evidence", {}).get("present") is True
            decision_hand = context.get("decision_hand", {})
            hero = decision_hand.get("hero", [])
            visible_hero = (
                seat == context.get("hero_seat", 6)
                and decision_hand.get("valid") is True
                and len(hero) == 2
                and len(set(hero)) == 2
                and all(re.fullmatch(r"[2-9TJQKA][shdc]", c) for c in hero)
            )
            presence_kind = "hero_cards" if visible_hero else "card_backs" if pair else None
            old_kind, sources = self.presence.get(seat, (None, []))
            sources = (
                (sources[-1:] if old_kind == presence_kind else []) + [self.source]
                if presence_kind
                else []
            )
            self.presence[seat] = presence_kind, sources
            if action or len(sources) == 2:
                participant = hand["participants"].setdefault(
                    str(seat),
                    {
                        "seat_index": seat,
                        "evidence": [],
                        "fold_observed": False,
                    },
                )
                evidence_kinds = (["action_label"] if action else []) + (
                    ["repeated_" + presence_kind] if len(sources) == 2 else []
                )
                for kind in evidence_kinds:
                    if not any(e["kind"] == kind for e in participant["evidence"]):
                        participant["evidence"].append(
                            {
                                "kind": kind,
                                **self.source,
                                "confirmation_frames": [self.source]
                                if kind == "action_label"
                                else sources,
                            }
                        )
                x, y, w, _ = slot["roi"]
                for player in row.get("players", []):
                    if (
                        player.get("name")
                        and player.get("confidence", 0) >= 85
                        and math.dist(player["roi"][:2], (x, y)) < w * 0.4
                    ):
                        names = participant.setdefault("observed_names", {})
                        names[player["name"]] = names.get(player["name"], 0) + 1
                if action == "fold":
                    participant["fold_observed"] = True
                elif action and participant["fold_observed"]:
                    hand["warnings"] = sorted(set(hand["warnings"] + ["action_after_fold"]))
            if action:
                # Confirming a street must not turn one continuous label into two actions.
                marker = action
                labels[seat] = marker
                previous = self.recent_labels.get(seat)
                bet = slot.get("current_bet")
                repeated = (
                    previous is not None
                    and previous["action"] == action
                    and previous["street"] == action_street
                    and action_street is not None
                    and type(bet) in (int, float)
                    and math.isfinite(bet)
                    and previous["bet"] == bet
                    and previous["epoch"] == self.action_epoch
                    and (at - previous["at"]).total_seconds() <= 1.25
                )
                if self.labels.get(seat) != marker:
                    if repeated:
                        previous["event"].setdefault("resumed_observations", []).append(
                            {
                                **self.source,
                                "evidence": label,
                                "reason": "short_gap_same_street_and_bet",
                            }
                        )
                    else:
                        self.emit(
                            "action_label",
                            seat_index=seat,
                            action=action,
                            street=action_street,
                            evidence=label,
                        )
                        if partial_river:
                            hand["events"][-1]["street_context"] = {
                                "method": "compatible_partial_river",
                                "previous_source": self.street_source,
                                "observed_board": list(board),
                            }
                        if self.street is None and proposed is not None:
                            hand["events"][-1]["street_candidate"] = {
                                "street": proposed,
                                "board_cards": list(board),
                            }
                        self.action_epoch += 1
                        previous = {"event": hand["events"][-1]}
                if previous is not None:
                    self.recent_labels[seat] = {
                        "action": action,
                        "street": action_street,
                        "bet": bet,
                        "epoch": self.action_epoch,
                        "at": at,
                        "event": previous["event"],
                    }
            elif sampled_action:
                labels.pop(seat, None)
                previous = self.recent_labels.get(seat)
                if previous and (
                    slot.get("current_bet") is None
                    or slot.get("current_bet") != previous["bet"]
                    or self.street != previous["street"]
                ):
                    self.recent_labels.pop(seat, None)
            blind = slot.get("blind_label") or {}
            kind = blind.get("blind")
            words = blind.get("words", [])
            if (
                kind in {"small_blind", "big_blind"}
                and words
                and min(w["confidence"] for w in words) >= 85
            ):
                old_kind, sources = self.blinds.get(seat, (None, []))
                sources = (sources[-1:] if old_kind == kind else []) + [self.source]
                self.blinds[seat] = kind, sources
                existing = [e for e in hand["events"] if e["kind"] == "blind_label"]
                if len(sources) == 2 and not any(
                    e["seat_index"] == seat and e["blind"] == kind for e in existing
                ):
                    if any(e["seat_index"] == seat for e in existing):
                        hand["warnings"] = sorted(set(hand["warnings"] + ["blind_conflict"]))
                    self.emit(
                        "blind_label",
                        seat_index=seat,
                        blind=kind,
                        street=self.street,
                        evidence=blind,
                        confirmation_frames=sources,
                    )
            else:
                self.blinds.pop(seat, None)
            self.amount((seat, self.street), slot.get("current_bet"))
        self.labels = labels
        for seat in set(self.presence) - present:
            self.presence.pop(seat)
        for key in list(self.amounts):
            if key[0] != "pot" and key[0] not in present:
                self.amounts.pop(key, None)
                self.baselines.pop(key, None)
        if signals.get("pot_sampled", True):
            self.amount(("pot", self.street), signals.get("pot", {}).get("value"))

    def emit(self, kind, **data):
        self.current["events"].append({"kind": kind, **self.source, **data})

    def amount(self, key, value):
        at = datetime.fromisoformat(self.source["captured_at"])
        previous_at = self.amount_times.get(key)
        if previous_at and (at - previous_at).total_seconds() > 10:
            self.amounts.pop(key, None)
            self.baselines.pop(key, None)
        self.amount_times[key] = at
        if (
            self.street is None
            or type(value) not in (int, float)
            or not math.isfinite(value)
            or value < 0
        ):
            self.amounts.pop(key, None)
            self.baselines.pop(key, None)
            return
        value = round(value, 2)
        old, count, first_source = self.amounts.get(key, (None, 0, None))
        first_source = first_source if old == value else self.source
        count = count + 1 if old == value else 1
        self.amounts[key] = value, count, first_source
        if count != 2:
            return
        previous, previous_source = self.baselines.get(key, (None, None))
        self.emit(
            "pot_amount" if key[0] == "pot" else "bet_amount",
            seat_index=None if key[0] == "pot" else key[0],
            street=self.street,
            value=value,
            previous=previous,
            observed_delta=round(value - previous, 2) if previous is not None else None,
            confirmation_frames=[first_source, self.source],
            previous_source=previous_source,
        )
        self.baselines[key] = value, self.source
