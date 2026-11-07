"""Current-state policy input, separate from the strict diagnostic advisor v1.

History and profiles are retained only as provenance, never policy features.
Only hand contributions and folded-player stacks may be unknown. The source
must explicitly attest the supported rules and a single-pot state.
"""

from copy import deepcopy
from dataclasses import dataclass, fields, replace

from poker.learning.advisor_adapters import from_engine
from poker.learning.advisor_contract import (
    ACTIONS,
    AdvisorObservation,
    AdvisorPlayer,
)
from poker.learning.advisor_contract import (
    VERSION as ADVISOR_VERSION,
)

VERSION = "snapshot-observation/1"
RULESET = "nlhe-cash-no-ante-no-straddle-no-bomb-pot/1"
VERSION_V2 = "snapshot-observation/2"
MIXED_RULESET = "nlhe-cash-standard-or-single-board-bomb-no-straddle/1"
BOMB_VARIANT = "bomb-pot-single-board/1"
MAX_PLAYERS = 7
MAX_AMOUNT = 10**12


class SnapshotRejected(ValueError):
    def __init__(self, reasons):
        self.reasons = tuple(sorted(set(reasons)))
        super().__init__("Snapshot rejected: " + ", ".join(self.reasons))


@dataclass
class SnapshotObservation(AdvisorObservation):
    schema_version: str = VERSION
    ruleset: str | None = None
    pot_structure: str | None = None

    supported_schema = VERSION
    supported_ruleset = RULESET

    def blocking_reasons(self):
        # Reuse structural checks without changing AdvisorObservation's v1 gate.
        base = replace(self, schema_version=ADVISOR_VERSION, source_blockers=[])
        reasons = set(AdvisorObservation.blocking_reasons(base))
        reasons.discard("history_incomplete")
        for player in self.players:
            if player.hand_contribution is None:
                reasons.discard(f"player.{player.seat}.hand_contribution_unknown_or_invalid")
            if player.folded is True and player.stack is None:
                reasons.discard(f"player.{player.seat}.stack_unknown_or_invalid")
        # Explicit producer refusals are never relaxed by optional-field rules.
        reasons.update(self.source_blockers)
        if self.schema_version != self.supported_schema:
            reasons.add("schema_version_unsupported")
        if self.ruleset != self.supported_ruleset:
            reasons.add("ruleset_unverified_or_unsupported")
        if self.pot_structure != "single":
            reasons.add("pot_structure_unverified_or_unsupported")
        if len(self.players) > MAX_PLAYERS:
            reasons.add("too_many_players")
        if type(self.hero_seat) is not int or type(self.dealer_seat) is not int:
            reasons.add("seats_unverified")
        if self.clockwise_seats is not None and any(
            type(s) is not int for s in self.clockwise_seats
        ):
            reasons.add("seat_order_unverified")
        amounts = [self.big_blind, self.pot, self.legal.get("call_delta")]
        amounts.extend(
            self.legal.get(f"{a}_to_{bound}") for a in ("bet", "raise") for bound in ("min", "max")
        )
        for player in self.players:
            amounts.extend((player.stack, player.street_contribution, player.hand_contribution))
            if player.cards_dealt is not True:
                reasons.add(f"player.{player.seat}.not_confirmed_participant")
            if player.all_in is True or (player.folded is False and player.stack == 0):
                reasons.add("existing_all_in_unsupported")
        if any(type(v) is int and v > MAX_AMOUNT for v in amounts):
            reasons.add("money_out_of_supported_range")
        if (
            all(type(p.hand_contribution) is int for p in self.players)
            and sum(p.hand_contribution for p in self.players) != self.pot
        ):
            reasons.add("pot_contributions_mismatch")
        if sum(p.folded is False for p in self.players) < 2:
            reasons.add("fewer_than_two_active_players")
        hero = next((p for p in self.players if p.seat == self.hero_seat), None)
        if (
            hero is not None
            and type(hero.stack) is int
            and hero.stack > 0
            and all(type(p.street_contribution) is int for p in self.players)
        ):
            target = max(p.street_contribution for p in self.players)
            facing = max(0, target - hero.street_contribution)
            if self.legal.get("call_delta") != min(facing, hero.stack):
                reasons.add("call_contributions_mismatch")
            flags = self.legal.get("actions", {})
            for action in ("bet", "raise"):
                if flags.get(action) is not True:
                    continue
                low, high = (self.legal.get(f"{action}_to_{b}") for b in ("min", "max"))
                if type(low) is not int or type(high) is not int:
                    continue
                if high != hero.stack + hero.street_contribution:
                    reasons.add(action + "_maximum_stack_mismatch")
                if low <= target:
                    reasons.add(action + "_minimum_not_above_target")
                if action == "bet" and target != 0:
                    reasons.add("bet_with_existing_wager")
        return sorted(reasons)

    def require_valid(self):
        reasons = self.blocking_reasons()
        if reasons:
            raise SnapshotRejected(reasons)
        return self


@dataclass
class VariantSnapshotObservation(SnapshotObservation):
    """Explicit single-board variant; V1 observations and weights stay unchanged."""

    schema_version: str = VERSION_V2
    hand_variant: str | None = None
    forced_ante: int | None = None

    supported_schema = VERSION_V2
    supported_ruleset = MIXED_RULESET

    def blocking_reasons(self) -> list[str]:
        reasons = set(super().blocking_reasons())
        if self.hand_variant not in ("standard", BOMB_VARIANT):
            reasons.add("hand_variant_unsupported")
        if self.hand_variant == "standard":
            if type(self.forced_ante) is not int or self.forced_ante != 0:
                reasons.add("standard_forced_ante_not_zero")
        elif self.hand_variant == BOMB_VARIANT:
            if type(self.forced_ante) is not int or not 0 < self.forced_ante <= MAX_AMOUNT:
                reasons.add("forced_ante_invalid")
            else:
                if (
                    type(self.pot) is int and self.pot < len(self.players) * self.forced_ante
                ) or any(
                    type(p.hand_contribution) is int and p.hand_contribution < self.forced_ante
                    for p in self.players
                ):
                    reasons.add("forced_ante_contributions_mismatch")
            if self.street == "preflop" or any(
                isinstance(e, dict) and e.get("street") == "preflop" for e in self.history
            ):
                reasons.add("bomb_pot_preflop_unsupported")
        return sorted(reasons)


def from_advisor(observation, *, ruleset, pot_structure):
    """Explicit projection; the original schema and all source blockers survive."""
    if type(observation) is not AdvisorObservation or observation.schema_version != ADVISOR_VERSION:
        raise ValueError("Expected advisor-observation/1")
    values = {
        f.name: deepcopy(getattr(observation, f.name))
        for f in fields(observation)
        if f.name != "schema_version"
    }
    return SnapshotObservation(**values, ruleset=ruleset, pot_structure=pot_structure)


def from_public_state(state, legal, *, hand_id, observation_id, big_blind, ruleset, quantum="1"):
    """Adapter for the public engine API; no GameState, deck or opponent hole cards."""
    observation = from_engine(
        state,
        legal,
        hand_id=hand_id,
        observation_id=observation_id,
        big_blind=big_blind,
        quantum=quantum,
        history_complete=True,
    )
    if ruleset == MIXED_RULESET:
        from poker.learning.advisor_contract import minor_units

        variant = getattr(state, "hand_variant", None)
        ante = getattr(state, "forced_ante", None)
        valid_variant = (variant == "standard" and ante is None) or (
            variant == BOMB_VARIANT and type(ante) is int and ante > 0
        )
        if valid_variant:
            observation.source_blockers = [
                b for b in observation.source_blockers if b != "hand_variant_unsupported"
            ]
        else:
            observation.source_blockers.append("hand_variant_unsupported")
        values = {
            f.name: deepcopy(getattr(observation, f.name))
            for f in fields(observation)
            if f.name != "schema_version"
        }
        return VariantSnapshotObservation(
            **values,
            ruleset=ruleset,
            pot_structure="single",
            hand_variant=variant,
            forced_ante=0 if variant == "standard" and ante is None else minor_units(ante, quantum),
        )
    # Existing all-ins are rejected independently, even when their pot is still single.
    return from_advisor(observation, ruleset=ruleset, pot_structure="single")


def from_dict(data):
    """Strict wire shape: reject unknown/private fields instead of silently ignoring them."""
    try:
        if not isinstance(data, dict) or data.get("schema_version") not in (VERSION, VERSION_V2):
            raise ValueError("Expected a supported snapshot observation version")
        cls = (
            SnapshotObservation if data["schema_version"] == VERSION else VariantSnapshotObservation
        )
        required = {f.name for f in fields(cls)}
        if set(data) != required:
            raise ValueError("Unexpected or missing snapshot fields")
        player_fields = {f.name for f in fields(AdvisorPlayer)}
        if not isinstance(data["players"], list) or any(
            not isinstance(p, dict) or set(p) != player_fields for p in data["players"]
        ):
            raise ValueError("Unexpected or missing player fields")
        for key in ("hero_cards", "board", "history", "source_blockers"):
            if not isinstance(data[key], list):
                raise ValueError("Expected a list: " + key)
        if not all(isinstance(s, str) for s in data["source_blockers"]):
            raise ValueError("Invalid source blockers")
        if any(not isinstance(c, str) for c in data["hero_cards"] + data["board"]):
            raise ValueError("Invalid cards")
        if data["clockwise_seats"] is not None and (
            not isinstance(data["clockwise_seats"], list)
            or any(type(s) is not int for s in data["clockwise_seats"])
        ):
            raise ValueError("Invalid seat order")
        if any(type(p["seat"]) is not int for p in data["players"]):
            raise ValueError("Invalid seat")
        legal = data["legal"]
        if not isinstance(legal, dict) or set(legal) != {
            "actions",
            "call_delta",
            "bet_to_min",
            "bet_to_max",
            "raise_to_min",
            "raise_to_max",
        }:
            raise ValueError("Invalid legal fields")
        if not isinstance(legal["actions"], dict) or set(legal["actions"]) != set(ACTIONS):
            raise ValueError("Invalid action flags")
        values = deepcopy(data)
        values["players"] = [AdvisorPlayer(**p) for p in values["players"]]
        result = cls(**values)
        result.require_valid()
        return result
    except (TypeError, KeyError, AttributeError) as error:
        raise ValueError("Malformed snapshot") from error
