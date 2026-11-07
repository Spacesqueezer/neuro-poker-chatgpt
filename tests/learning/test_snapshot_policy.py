import json
from copy import deepcopy
from dataclasses import replace

import pytest

from poker.learning.advisor_adapters import from_hud
from poker.learning.advisor_contract import ACTIONS, AdvisorObservation
from poker.learning.snapshot_actions import decode, target
from poker.learning.snapshot_contract import (
    RULESET,
    SnapshotRejected,
    from_advisor,
    from_dict,
)
from poker.learning.snapshot_encoding import PLAYER_FEATURES, TABLE_FEATURES, encode
from tests.learning.test_advisor_contract import observations


def sample():
    return from_advisor(observations()[0], ruleset=RULESET, pot_structure="single")


def numeric(encoded):
    return encoded.table, encoded.players, encoded.seat_mask, encoded.action_mask


def test_versioned_round_trip_and_explicit_optional_fields_do_not_relax_legacy_gate():
    original = observations()[0]
    original.history_complete = False
    for p in original.players:
        p.hand_contribution = None
    assert "history_incomplete" in original.blocking_reasons()
    current = from_advisor(original, ruleset=RULESET, pot_structure="single")
    current.require_valid()
    wire = json.loads(json.dumps(current.to_dict()))
    assert from_dict(wire).to_dict() == current.to_dict()
    assert current.players[0] is not original.players[0]
    assert original.schema_version == "advisor-observation/1"
    with pytest.raises(ValueError):
        encode(original)
    assert type(original) is AdvisorObservation


def test_only_public_numeric_state_is_encoded():
    current = sample()
    before = numeric(encode(current))
    current.hand_id, current.observation_id = "different", "frame:99"
    current.source, current.captured_at = "hud", "2026-11-04T00:00:00Z"
    current.history, current.history_complete = [{"private": "must not enter features"}], False
    current.evidence = {"deck": ["As", "Ah"]}
    for p in current.players:
        p.name, p.position, p.statistics = "other nickname", "ignored", {"vpip": 0.99}
    assert numeric(encode(current)) == before


def test_seat_renumbering_rotation_and_input_list_order_do_not_change_features():
    current = sample()
    before = numeric(encode(current))
    mapping = {s: 40 + i * 3 for i, s in enumerate(current.clockwise_seats)}
    current.hero_seat, current.dealer_seat = (
        mapping[current.hero_seat],
        mapping[current.dealer_seat],
    )
    order = [mapping[s] for s in current.clockwise_seats]
    current.clockwise_seats = order[1:] + order[:1]
    for p in current.players:
        p.seat = mapping[p.seat]
    current.players.reverse()
    assert numeric(encode(current)) == before


def test_money_currency_scale_is_invariant_and_optional_zero_differs_from_unknown():
    current = sample()
    before = numeric(encode(current))
    current.quantum = "0.01"
    current.big_blind *= 100
    current.pot *= 100
    for key in current.legal:
        if key != "actions" and current.legal[key] is not None:
            current.legal[key] *= 100
    for p in current.players:
        for key in ("stack", "street_contribution", "hand_contribution"):
            setattr(p, key, getattr(p, key) * 100)
    assert numeric(encode(current)) == before
    current.players[0].hand_contribution = None
    row = encode(current)
    i = row.seat_order.index(current.players[0].seat)
    assert row.players[i][PLAYER_FEATURES.index("hand_contribution.known")] == 0
    assert len(row.table) == len(TABLE_FEATURES)
    assert len(row.players) == len(row.seat_mask) == 7
    assert all(not any(p) for p, mask in zip(row.players, row.seat_mask, strict=True) if not mask)


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("ruleset", None, "ruleset_unverified_or_unsupported"),
        ("ruleset", "bomb-pot", "ruleset_unverified_or_unsupported"),
        ("pot_structure", "side_pots", "pot_structure_unverified_or_unsupported"),
        ("schema_version", "snapshot-observation/99", "schema_version_unsupported"),
        ("big_blind", None, "big_blind_unknown_or_invalid"),
        ("clockwise_seats", None, "seat_order_unverified"),
        ("is_my_turn", False, "not_confirmed_hero_turn"),
        ("pot", 999, "pot_contributions_mismatch"),
    ],
)
def test_refuse_unsupported_or_incomplete_current_state(field, value, reason):
    current = sample()
    setattr(current, field, value)
    with pytest.raises(SnapshotRejected) as caught:
        encode(current)
    assert reason in caught.value.reasons


def test_source_blockers_survive_even_when_they_match_optional_field_errors():
    current = sample()
    current.history_complete = False
    current.source_blockers = ["history_incomplete", "stacks_unverified"]
    with pytest.raises(SnapshotRejected) as caught:
        encode(current)
    assert set(current.source_blockers) <= set(caught.value.reasons)
    hud = from_hud({}, hand_id="1", observation_id="1", captured_at=None)
    projected = from_advisor(hud, ruleset=RULESET, pot_structure="single")
    assert "hud_state_reconstruction_unverified" in projected.blocking_reasons()


def test_active_stacks_and_contradictory_calls_cannot_be_masked():
    current = sample()
    hero = next(p for p in current.players if p.seat == current.hero_seat)
    hero.stack = None
    with pytest.raises(SnapshotRejected):
        encode(current)
    hero.stack, hero.all_in = 0, True
    assert "existing_all_in_unsupported" in current.blocking_reasons()
    current = sample()
    current.legal["call_delta"] += 1
    assert "call_contributions_mismatch" in current.blocking_reasons()


def test_unknown_folded_stack_is_masked_but_not_a_missing_active_stack():
    current = sample()
    # Add a third dealt player, already folded, without inventing its remaining stack.
    folded = replace(
        current.players[0],
        seat=99,
        stack=None,
        folded=True,
        street_contribution=0,
        hand_contribution=None,
    )
    current.players.append(folded)
    current.clockwise_seats.append(99)
    features = encode(current)
    row = features.players[features.seat_order.index(99)]
    assert row[PLAYER_FEATURES.index("stack.known")] == 0
    folded.folded = False
    with pytest.raises(SnapshotRejected):
        encode(current)


@pytest.mark.parametrize("damage", ["private_card", "version", "actions", "cards", "seat_order"])
def test_wire_rejects_unknown_fields_and_malformed_data(damage):
    data = sample().to_dict()
    if damage == "private_card":
        data["players"][0]["hole_cards"] = ["Ah", "As"]
    elif damage == "version":
        data["schema_version"] = "advisor-observation/1"
    elif damage == "actions":
        data["legal"]["actions"] = []
    elif damage == "cards":
        data["hero_cards"] = [{}]
    else:
        data["clockwise_seats"] = [None, []]
    with pytest.raises(ValueError):
        from_dict(data)


def test_range_sizing_round_trip_endpoints_midpoints_and_amount_semantics():
    for original in observations():
        current = from_advisor(original, ruleset=RULESET, pot_structure="single")
        for action in ACTIONS:
            if not current.legal["actions"][action]:
                continue
            if action in ("bet", "raise"):
                low, high = (current.legal[f"{action}_to_{b}"] for b in ("min", "max"))
                for value in {low, high, (low + high) // 2}:
                    index, fraction, sized = target(current, action, value)
                    decision = decode(current, index, fraction)
                    assert sized and decision.amount_to == value and decision.call_delta is None
            else:
                index, fraction, sized = target(current, action)
                decision = decode(current, index, fraction)
                assert not sized and decision.amount_to is None
                assert decision.call_delta == (
                    current.legal["call_delta"] if action == "call" else None
                )
            assert decision.observation_id == current.observation_id


@pytest.mark.parametrize("fraction", [-0.1, 1.1, float("nan"), float("inf"), True])
def test_decoder_never_clamps_malformed_outputs(fraction):
    current = sample()
    index = next(i for i, a in enumerate(ACTIONS) if current.legal["actions"][a])
    with pytest.raises(ValueError):
        decode(current, index, fraction)


def test_decoder_rejects_illegal_action_and_changed_state():
    current = sample()
    forbidden = next(i for i, a in enumerate(ACTIONS) if not current.legal["actions"][a])
    with pytest.raises(ValueError):
        decode(current, forbidden, 0.5)
    allowed = next(i for i, a in enumerate(ACTIONS) if current.legal["actions"][a])
    changed = deepcopy(current)
    changed.is_my_turn = False
    with pytest.raises(SnapshotRejected):
        decode(changed, allowed, 0.5)
