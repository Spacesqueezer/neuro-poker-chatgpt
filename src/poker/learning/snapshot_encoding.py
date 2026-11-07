"""Pure, versioned snapshot features. No torch, databases or nickname identity."""

import hashlib
import json
import math
from dataclasses import dataclass

from poker.learning.advisor_contract import ACTIONS, BOARD_COUNTS
from poker.learning.snapshot_card_features import CARD_FEATURES, SEMANTICS, card_features
from poker.learning.snapshot_contract import (
    BOMB_VARIANT,
    MAX_PLAYERS,
    VERSION,
    VERSION_V2,
    SnapshotObservation,
    SnapshotRejected,
    VariantSnapshotObservation,
)

ENCODING = "snapshot-features/1"
CARDS = tuple(rank + suit for rank in "23456789TJQKA" for suit in "cdhs")
MONEY_FIELDS = ("call_delta", "bet_to_min", "bet_to_max", "raise_to_min", "raise_to_max")
TABLE_FEATURES = (
    *("street." + s for s in BOARD_COUNTS),
    *("hero." + c for c in CARDS),
    *("board." + c for c in CARDS),
    "pot.log_bb",
    "players.fraction",
    "active.fraction",
    *("legal." + name + ".log_bb" for name in MONEY_FIELDS),
)
PLAYER_FEATURES = (
    "relative_clockwise",
    "is_hero",
    "is_dealer",
    "folded",
    "stack.log_bb",
    "stack.known",
    "street_contribution.log_bb",
    "hand_contribution.log_bb",
    "hand_contribution.known",
)
LAYOUT = {
    "encoding": ENCODING,
    "observation": VERSION,
    "max_players": MAX_PLAYERS,
    "table_features": list(TABLE_FEATURES),
    "player_features": list(PLAYER_FEATURES),
    "action_order": list(ACTIONS),
    "money_transform": "log1p(amount / big_blind)",
    "seat_order": "hero_first_then_clockwise",
    "padding": "zero_with_seat_mask",
    "history_used": False,
    "profiles_used": False,
}
LAYOUT_SHA256 = hashlib.sha256(json.dumps(LAYOUT, sort_keys=True).encode()).hexdigest()
FEATURE_SETS = ("raw-v1", "cards-v2", "variants-v3")
LAYOUT_V2 = {
    **LAYOUT,
    "encoding": "snapshot-features/2",
    "table_features": [*TABLE_FEATURES, *CARD_FEATURES],
    "card_facts": SEMANTICS,
}
LAYOUT_V2_SHA256 = hashlib.sha256(json.dumps(LAYOUT_V2, sort_keys=True).encode()).hexdigest()
LAYOUT_V3 = {
    **LAYOUT_V2,
    "encoding": "snapshot-features/3",
    "observation": VERSION_V2,
    "table_features": [*TABLE_FEATURES, *CARD_FEATURES, "variant.bomb_pot", "forced_ante.log_bb"],
    "variant_semantics": "standard_zero_ante_or_equal_dead_ante_no_blinds_immediate_single_flop/1",
}
LAYOUT_V3_SHA256 = hashlib.sha256(json.dumps(LAYOUT_V3, sort_keys=True).encode()).hexdigest()


def layout_for(feature_set):
    if feature_set not in FEATURE_SETS:
        raise ValueError("Unsupported snapshot feature set")
    return {"raw-v1": LAYOUT, "cards-v2": LAYOUT_V2, "variants-v3": LAYOUT_V3}[feature_set]


def layout_hash(feature_set):
    layout_for(feature_set)
    return {
        "raw-v1": LAYOUT_SHA256,
        "cards-v2": LAYOUT_V2_SHA256,
        "variants-v3": LAYOUT_V3_SHA256,
    }[feature_set]


def feature_set_of(encoded):
    for name in FEATURE_SETS:
        layout = layout_for(name)
        if encoded.encoding == layout["encoding"] and encoded.layout_sha256 == layout_hash(name):
            if len(encoded.table) != len(layout["table_features"]):
                raise ValueError("Invalid encoded table width")
            return name
    raise ValueError("Incompatible encoded layout")


@dataclass(frozen=True)
class EncodedSnapshot:
    table: tuple[float, ...]
    players: tuple[tuple[float, ...], ...]
    seat_mask: tuple[float, ...]
    action_mask: tuple[float, ...]
    # Provenance is deliberately outside the numeric inputs.
    seat_order: tuple[int, ...]
    hand_id: str
    observation_id: str
    encoding: str = ENCODING
    layout_sha256: str = LAYOUT_SHA256


def encode(observation, *, feature_set="raw-v1"):
    layout = layout_for(feature_set)
    expected = VariantSnapshotObservation if feature_set == "variants-v3" else SnapshotObservation
    if type(observation) is not expected:
        raise SnapshotRejected(["model_observation_version_mismatch"])
    observation.require_valid()
    order = observation.clockwise_seats
    start = order.index(observation.hero_seat)
    order = order[start:] + order[:start]
    by_seat = {p.seat: p for p in observation.players}

    def amount(value):
        return 0.0 if value is None else math.log1p(value / observation.big_blind)

    flags = observation.legal["actions"]
    # Bounds for an unavailable action are not data and cannot affect the policy.
    money = [observation.legal["call_delta"]]
    for action in ("bet", "raise"):
        money.extend(
            observation.legal[f"{action}_to_{b}"] if flags[action] else None for b in ("min", "max")
        )
    table = (
        *(float(observation.street == s) for s in BOARD_COUNTS),
        *(float(c in observation.hero_cards) for c in CARDS),
        *(float(c in observation.board) for c in CARDS),
        amount(observation.pot),
        len(order) / MAX_PLAYERS,
        sum(not p.folded for p in observation.players) / MAX_PLAYERS,
        *(amount(v) for v in money),
    )
    if feature_set in ("cards-v2", "variants-v3"):
        table += card_features(observation.hero_cards, observation.board)
    if feature_set == "variants-v3":
        assert isinstance(observation, VariantSnapshotObservation)
        table += (float(observation.hand_variant == BOMB_VARIANT), amount(observation.forced_ante))
    players = []
    for relative, seat in enumerate(order):
        p = by_seat[seat]
        players.append(
            (
                relative / MAX_PLAYERS,
                float(relative == 0),
                float(seat == observation.dealer_seat),
                float(p.folded),
                amount(p.stack),
                float(p.stack is not None),
                amount(p.street_contribution),
                amount(p.hand_contribution),
                float(p.hand_contribution is not None),
            )
        )
    padding = MAX_PLAYERS - len(order)
    players.extend([(0.0,) * len(PLAYER_FEATURES)] * padding)
    return EncodedSnapshot(
        table=table,
        players=tuple(players),
        seat_mask=(1.0,) * len(order) + (0.0,) * padding,
        action_mask=tuple(float(flags[a]) for a in ACTIONS),
        seat_order=tuple(order),
        hand_id=observation.hand_id,
        observation_id=observation.observation_id,
        encoding=layout["encoding"],
        layout_sha256=layout_hash(feature_set),
    )
