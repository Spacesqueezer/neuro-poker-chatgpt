"""Explicit sizing policies, separate from the learned choice of action.

expert-pot65-v1 reproduces the current heuristic teacher's amount formula.
It is a transparent baseline, not a learned size or a claim of optimal poker.
"""

# Existing snapshot codecs are runtime-validated but do not yet have annotations.
# mypy: disable-error-code="no-untyped-call"

from dataclasses import replace
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any, cast

from poker.learning.advisor_contract import ACTIONS
from poker.learning.snapshot_actions import SnapshotDecision, bounds, decode
from poker.learning.snapshot_contract import SnapshotObservation

SIZING_POLICIES = ("neural-range-v1", "expert-pot65-v1")


def sized_decision(
    observation: SnapshotObservation,
    action_index: int,
    *,
    policy: str,
    neural_fraction: float | None = None,
) -> tuple[SnapshotDecision, dict[str, Any]]:
    """Return a legal decision and auditable arithmetic; never replace an action."""
    if policy not in SIZING_POLICIES:
        raise ValueError("Unknown sizing policy; choose one explicitly")
    if policy == "neural-range-v1":
        return decode(observation, action_index, neural_fraction), {
            "policy": policy,
            "neural_fraction": neural_fraction,
        }
    # This validates the complete state, the action index and its availability.
    decision = decode(observation, action_index, 0.0)
    action = ACTIONS[action_index]
    trace: dict[str, Any] = {"policy": policy, "learned_amount": False}
    if action not in ("bet", "raise"):
        return decision, trace
    low, high = bounds(observation, action)
    # decode above has rejected missing/non-integer contributions and pot.
    current_target = max(cast(int, p.street_contribution) for p in observation.players)
    increment = low if action == "bet" else low - current_target
    base = max(cast(int, observation.pot), increment)
    # Amounts are integer quantum units. Exact decimal rounding reproduces the
    # teacher's ties-to-even convention, not the range decoder's half-up rule.
    rounded = int((Decimal(base) * Decimal("0.65")).to_integral_value(rounding=ROUND_HALF_EVEN))
    unbounded = rounded + (current_target if action == "raise" else 0)
    amount = min(high, max(low, unbounded))
    trace.update(
        pot=observation.pot,
        current_target=current_target,
        minimum_increment=increment,
        formula_base=base,
        ratio="0.65",
        rounding="half_even_to_one_quantum",
        rounded_increment=rounded,
        amount_before_bounds=unbounded,
        minimum_to=low,
        maximum_to=high,
        amount_to=amount,
        bounded_by="minimum" if unbounded < low else "maximum" if unbounded > high else None,
    )
    return replace(decision, amount_to=amount), trace
