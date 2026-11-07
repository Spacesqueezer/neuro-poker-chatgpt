"""Versioned, model-independent observations. No inference or action execution."""

import re
from dataclasses import asdict, dataclass, field
from decimal import Decimal, InvalidOperation

VERSION = "advisor-observation/1"
ACTIONS = ("fold", "check", "call", "bet", "raise", "all_in")
BOARD_COUNTS = {"preflop": 0, "flop": 3, "turn": 4, "river": 5}


def minor_units(value, quantum):
    """Convert without rounding; 0.01 currency and one engine chip are distinct units."""
    if value is None:
        return None
    if isinstance(value, bool) or isinstance(quantum, bool):
        raise ValueError("Boolean is not a monetary amount")
    try:
        amount, unit = Decimal(str(value)), Decimal(str(quantum))
        if not amount.is_finite() or not unit.is_finite() or unit <= 0 or amount < 0:
            raise ValueError("Amounts must be nonnegative and quantum positive")
        result = amount / unit
        if result != result.to_integral_value():
            raise ValueError("Amount is not a multiple of quantum")
        return int(result)
    except (InvalidOperation, ZeroDivisionError) as exc:
        raise ValueError("Invalid monetary amount") from exc


@dataclass
class AdvisorPlayer:
    seat: int
    name: str | None
    stack: int | None
    street_contribution: int | None
    hand_contribution: int | None
    cards_dealt: bool | None
    folded: bool | None
    all_in: bool | None
    position: str | None = None
    # Future metrics must include their observation/opportunity counts.
    statistics: dict = field(default_factory=dict)


@dataclass
class AdvisorObservation:
    source: str
    hand_id: str
    observation_id: str
    captured_at: str | None
    quantum: str
    big_blind: int | None
    hero_seat: int
    dealer_seat: int | None
    clockwise_seats: list[int] | None
    is_my_turn: bool | None
    street: str | None
    hero_cards: list[str]
    board: list[str]
    pot: int | None
    players: list[AdvisorPlayer]
    legal: dict
    history: list[dict]
    history_complete: bool
    source_blockers: list[str] = field(default_factory=list)
    evidence: dict = field(default_factory=dict)
    schema_version: str = VERSION

    def to_dict(self):
        return asdict(self)

    def blocking_reasons(self):
        """Conservative structural gate, not a poker-rule or perception validator."""
        errors = list(self.source_blockers)
        try:
            minor_units(0, self.quantum)
        except ValueError:
            errors.append("quantum_invalid")
        if self.schema_version != VERSION:
            errors.append("schema_version_unsupported")
        if not self.hand_id or not self.observation_id:
            errors.append("identity_missing")
        if self.is_my_turn is not True:
            errors.append("not_confirmed_hero_turn")
        if self.street not in BOARD_COUNTS or len(self.board) != BOARD_COUNTS.get(self.street):
            errors.append("street_board_mismatch")
        cards = self.hero_cards + self.board
        if (
            len(self.hero_cards) != 2
            or len(cards) != len(set(cards))
            or any(
                not isinstance(c, str) or not re.fullmatch(r"[2-9TJQKA][cdhs]", c) for c in cards
            )
        ):
            errors.append("cards_invalid")
        seats = [p.seat for p in self.players]
        if (
            not 2 <= len(seats) <= 9
            or len(set(seats)) != len(seats)
            or any(type(s) is not int or s < 0 for s in seats)
            or self.hero_seat not in seats
            or self.dealer_seat not in seats
        ):
            errors.append("seats_unverified")
        if (
            self.clockwise_seats is None
            or len(self.clockwise_seats) != len(seats)
            or set(self.clockwise_seats) != set(seats)
        ):
            errors.append("seat_order_unverified")
        if self.history_complete is not True:
            errors.append("history_incomplete")
        for key, value in (("pot", self.pot), ("big_blind", self.big_blind)):
            if type(value) is not int or value < (1 if key == "big_blind" else 0):
                errors.append(key + "_unknown_or_invalid")
        for p in self.players:
            for key in ("stack", "street_contribution", "hand_contribution"):
                value = getattr(p, key)
                if type(value) is not int or value < 0:
                    errors.append(f"player.{p.seat}.{key}_unknown_or_invalid")
            for key in ("cards_dealt", "folded", "all_in"):
                if type(getattr(p, key)) is not bool:
                    errors.append(f"player.{p.seat}.{key}_unknown")
            if (
                type(p.street_contribution) is int
                and type(p.hand_contribution) is int
                and p.street_contribution > p.hand_contribution
            ):
                errors.append(f"player.{p.seat}.contributions_inconsistent")
        flags = self.legal.get("actions", {})
        if any(type(flags.get(a)) is not bool for a in ACTIONS):
            errors.append("legal_actions_unknown")
        if not any(flags.get(a) is True for a in ACTIONS):
            errors.append("no_legal_action")
        for action in ("bet", "raise"):
            if flags.get(action) is True:
                lower, upper = (self.legal.get(action + "_to_" + k) for k in ("min", "max"))
                if type(lower) is not int or type(upper) is not int or not 0 < lower <= upper:
                    errors.append(action + "_bounds_unverified")
        call = self.legal.get("call_delta")
        if type(call) is not int or call < 0:
            errors.append("call_unknown_or_invalid")
        # Check contradictions among known fields even in incomplete HUD drafts.
        if flags.get("check") is True and flags.get("call") is True:
            errors.append("conflicting_check_call")
        if flags.get("bet") is True and flags.get("raise") is True:
            errors.append("conflicting_bet_raise")
        if type(call) is int and call >= 0:
            if flags.get("check") is True and call != 0:
                errors.append("check_with_call_amount")
            if flags.get("call") is True and call == 0:
                errors.append("call_without_amount")
        for player in self.players:
            if player.all_in is True and type(player.stack) is int and player.stack > 0:
                errors.append(f"player.{player.seat}.all_in_with_stack")
            if player.all_in is True and player.folded is True:
                errors.append(f"player.{player.seat}.folded_all_in")
            if (
                player.seat == self.hero_seat
                and self.is_my_turn is True
                and (player.folded is True or player.all_in is True or player.cards_dealt is False)
            ):
                errors.append("hero_cannot_act")
        return sorted(set(errors))
