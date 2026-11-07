from copy import deepcopy

import pytest

from poker.learning.advisor_contract import ACTIONS
from poker.learning.snapshot_actions import decode
from poker.learning.snapshot_contract import RULESET, SnapshotRejected, from_advisor
from poker.learning.snapshot_sizing import sized_decision
from tests.learning.test_advisor_contract import observations


def state(action="bet", *, pot=30, low=2, high=100, target=0):
    observation = from_advisor(
        next(o for o in observations() if o.street == "flop"),
        ruleset=RULESET,
        pot_structure="single",
    )
    hero = next(p for p in observation.players if p.seat == observation.hero_seat)
    villain = next(p for p in observation.players if p.seat != observation.hero_seat)
    for player in observation.players:
        player.hand_contribution, player.street_contribution = None, 0
    hero.stack, villain.street_contribution = high, target
    observation.pot = pot
    observation.legal = {
        "actions": {
            a: a in ("check", "bet", "all_in")
            if action == "bet"
            else a in ("fold", "call", "raise", "all_in")
            for a in ACTIONS
        },
        "call_delta": target,
        "bet_to_min": low if action == "bet" else None,
        "bet_to_max": high if action == "bet" else None,
        "raise_to_min": low if action == "raise" else None,
        "raise_to_max": high if action == "raise" else None,
    }
    observation.require_valid()
    return observation


@pytest.mark.parametrize(
    "pot,low,high,expected,limited",
    [
        (30, 2, 100, 20, None),
        (50, 2, 100, 32, None),
        (90, 2, 100, 58, None),
        (110, 2, 100, 72, None),
        (1, 2, 100, 2, "minimum"),
        (200, 2, 20, 20, "maximum"),
        (30, 2, 2, 2, "maximum"),
        (642, 10, 1842, 417, None),
        (10**12, 2, 10**12, 650000000000, None),
    ],
)
def test_exact_ties_to_even_bounds_and_large_integer_amounts(pot, low, high, expected, limited):
    observation = state(pot=pot, low=low, high=high)
    result, trace = sized_decision(observation, ACTIONS.index("bet"), policy="expert-pot65-v1")
    assert result.amount_to == expected and trace["amount_to"] == expected
    assert trace["bounded_by"] == limited and not trace["learned_amount"]
    assert result.action == "bet" and result.call_delta is None


def test_raise_returns_total_not_added_chips_and_ignores_cards_and_nicknames():
    observation = state("raise", pot=30, low=16, high=100, target=8)
    decision, trace = sized_decision(observation, ACTIONS.index("raise"), policy="expert-pot65-v1")
    assert decision.amount_to == 28 and trace["rounded_increment"] == 20
    assert trace["minimum_increment"] == 8 and trace["current_target"] == 8
    changed = deepcopy(observation)
    changed.hero_cards, changed.board = ["As", "Ah"], ["2c", "3d", "4h"]
    for player in changed.players:
        player.name, player.statistics = "different", {"hidden_target": "fold"}
    assert sized_decision(changed, ACTIONS.index("raise"), policy="expert-pot65-v1") == (
        decision,
        trace,
    )


def test_amounts_are_integer_quantum_units_and_passive_actions_preserve_semantics():
    observation = state(pot=3000, low=200, high=10000)
    observation.quantum = "0.01"
    assert sized_decision(observation, 3, policy="expert-pot65-v1")[0].amount_to == 1950
    for obs, actions in (
        (observation, ("check", "all_in")),
        (state("raise", pot=30, low=16, target=8), ("fold", "call", "all_in")),
    ):
        for action in actions:
            result, trace = sized_decision(obs, ACTIONS.index(action), policy="expert-pot65-v1")
            assert result == decode(obs, ACTIONS.index(action), 0.0)
            assert result.amount_to is None and "amount_to" not in trace


def test_neural_mode_is_unchanged_and_rule_never_substitutes_unavailable_action():
    observation = state()
    for fraction in (0.0, 0.12345, 0.5, 1.0):
        assert sized_decision(observation, 3, policy="neural-range-v1", neural_fraction=fraction)[
            0
        ] == decode(observation, 3, fraction)
    with pytest.raises(ValueError, match="Unavailable"):
        sized_decision(observation, 4, policy="expert-pot65-v1")
    with pytest.raises(ValueError, match="Invalid action"):
        sized_decision(observation, True, policy="expert-pot65-v1")
    with pytest.raises(ValueError, match="Unknown sizing"):
        sized_decision(observation, 3, policy="auto")
    observation.is_my_turn = False
    with pytest.raises(SnapshotRejected):
        sized_decision(observation, 3, policy="expert-pot65-v1")
