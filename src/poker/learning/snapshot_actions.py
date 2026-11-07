"""Identical range-relative sizing for supervised targets and decoded actions."""

import math
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from poker.learning.advisor_contract import ACTIONS


@dataclass(frozen=True)
class SnapshotDecision:
    hand_id: str
    observation_id: str
    action: str
    amount_to: int | None
    call_delta: int | None
    quantum: str


def bounds(observation, action):
    return tuple(observation.legal[f"{action}_to_{b}"] for b in ("min", "max"))


def target(observation, action, amount_to=None):
    observation.require_valid()
    if action not in ACTIONS or observation.legal["actions"].get(action) is not True:
        raise ValueError("Unavailable action")
    if action not in ("bet", "raise"):
        if amount_to is not None:
            raise ValueError("Only bet/raise carry amount_to")
        return ACTIONS.index(action), 0.0, False
    low, high = bounds(observation, action)
    if type(amount_to) is not int or not low <= amount_to <= high:
        raise ValueError("Amount outside the legal interval")
    return ACTIONS.index(action), (amount_to - low) / (high - low) if high > low else 0.0, True


def decode(observation, action_index, sizing_fraction):
    observation.require_valid()
    if type(action_index) is not int or not 0 <= action_index < len(ACTIONS):
        raise ValueError("Invalid action index")
    if type(sizing_fraction) not in (float, int) or not math.isfinite(sizing_fraction):
        raise ValueError("Invalid sizing fraction")
    if not 0 <= sizing_fraction <= 1:
        raise ValueError("Sizing fraction outside [0, 1]")
    action = ACTIONS[action_index]
    if observation.legal["actions"].get(action) is not True:
        raise ValueError("Unavailable action; no silent fallback")
    amount_to = None
    if action in ("bet", "raise"):
        low, high = bounds(observation, action)
        offset = (Decimal(str(sizing_fraction)) * (high - low)).to_integral_value(
            rounding=ROUND_HALF_UP
        )
        amount_to = low + int(offset)
    return SnapshotDecision(
        observation.hand_id,
        observation.observation_id,
        action,
        amount_to,
        observation.legal["call_delta"] if action == "call" else None,
        observation.quantum,
    )
