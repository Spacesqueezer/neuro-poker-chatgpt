from dataclasses import replace

import pytest

from poker.api import ActionDecision, play_hand
from poker.game.actions import PlayerAction
from poker.learning.advisor_adapters import from_engine, from_hud
from poker.learning.advisor_contract import minor_units


class Caller:
    def choose_action(self, state, legal):
        action = PlayerAction.CHECK if PlayerAction.CHECK in legal.actions else PlayerAction.CALL
        return ActionDecision(action, legal.call_amount if action == PlayerAction.CALL else 0)


def observations():
    result = []

    def observer(state, legal, decision):
        result.append(
            from_engine(
                state,
                legal,
                hand_id="test",
                observation_id=str(len(result)),
                big_blind=2,
                history_complete=True,
            )
        )

    play_hand({"hero": Caller(), "villain": Caller()}, seed=42, decision_observer=observer)
    return result


def test_real_engine_public_states_and_history_pass_structural_gate():
    rows = observations()
    assert {r.street for r in rows} == {"preflop", "flop", "turn", "river"}
    assert all(not r.blocking_reasons() for r in rows)
    assert rows[-1].history
    assert all(len(r.hero_cards) == 2 for r in rows)
    assert all("hole_cards" not in p for r in rows for p in r.to_dict()["players"])


@pytest.mark.parametrize(
    "value,unit,expected", [(15.5, "0.01", 1550), (0, "0.01", 0), (2, "1", 2), (None, "0.01", None)]
)
def test_exact_money(value, unit, expected):
    assert minor_units(value, unit) == expected


@pytest.mark.parametrize(
    "value,unit",
    [
        (True, "1"),
        (-1, "1"),
        ("NaN", "1"),
        ("Infinity", "1"),
        (1.001, "0.01"),
        (1, "0"),
        (1, "NaN"),
    ],
)
def test_no_rounding_or_nonfinite_amounts(value, unit):
    with pytest.raises(ValueError):
        minor_units(value, unit)


def test_hud_unknowns_and_source_blockers_survive_without_name_identity():
    req = dict(
        is_my_turn=True,
        street_name="preflop",
        hero_hole_cards=["Ah", "As"],
        board_cards=[],
        total_pot=15.5,
        call_amount_needed=2.5,
        players=[
            dict(
                seat_index=6,
                name="",
                stack=None,
                current_bet=None,
                cards_dealt=True,
                is_active=False,
                is_dealer=True,
            )
        ],
    )
    row = from_hud(
        req,
        hand_id="123",
        observation_id="frame:1",
        captured_at="2026-10-06T00:00:00Z",
        blockers=["stale"],
    )
    assert row.pot == 1550
    assert row.players[0].stack is None
    assert row.players[0].folded is None
    assert row.players[0].name is None
    assert row.history == [] and not row.history_complete
    assert {"stale", "hud_state_reconstruction_unverified", "history_incomplete"} <= set(
        row.blocking_reasons()
    )
    assert req["players"][0]["current_bet"] is None


def test_optional_names_and_stats_do_not_block_complete_engine_state():
    row = observations()[0]
    row.players = [replace(p, name=None, statistics={}) for p in row.players]
    assert not row.blocking_reasons()


def test_invalid_cards_and_unknown_legal_flag_block():
    row = observations()[0]
    row.hero_cards = ["Ah", "Ah"]
    row.legal["actions"]["all_in"] = None
    assert {"cards_invalid", "legal_actions_unknown"} <= set(row.blocking_reasons())


def test_hud_and_engine_amounts_share_semantics():
    engine = observations()[0]
    request = dict(
        is_my_turn=True,
        street_name=engine.street,
        hero_hole_cards=engine.hero_cards,
        board_cards=engine.board,
        total_pot=engine.pot / 100,
        call_amount_needed=engine.legal["call_delta"] / 100,
        min_raise_amount=engine.legal["raise_to_min"] / 100,
        max_raise_amount=engine.legal["raise_to_max"] / 100,
        players=[
            dict(
                seat_index=p.seat,
                name=p.name,
                stack=p.stack / 100,
                current_bet=p.street_contribution / 100,
                cards_dealt=True,
                is_dealer=p.seat == engine.dealer_seat,
            )
            for p in engine.players
        ],
        **{"can_" + a: v for a, v in engine.legal["actions"].items()},
    )
    hud = from_hud(
        request, hand_id="x", observation_id="y", captured_at=None, hero_seat=engine.hero_seat
    )
    assert hud.pot == engine.pot
    assert hud.legal == engine.legal
    assert [p.stack for p in hud.players] == [p.stack for p in engine.players]


@pytest.mark.parametrize(
    "change,expected",
    [
        ("check_call", "conflicting_check_call"),
        ("bet_raise", "conflicting_bet_raise"),
        ("check_amount", "check_with_call_amount"),
        ("call_zero", "call_without_amount"),
        ("hero_folded", "hero_cannot_act"),
        ("hero_undealt", "hero_cannot_act"),
        ("hero_all_in", "hero_cannot_act"),
        ("all_in_stack", "all_in_with_stack"),
        ("folded_all_in", "folded_all_in"),
    ],
)
def test_known_contradictions_block_even_when_other_fields_are_unknown(change, expected):
    row = observations()[0]
    row.big_blind = None
    flags = row.legal["actions"]
    hero = next(p for p in row.players if p.seat == row.hero_seat)
    if change == "check_call":
        flags.update(check=True, call=True)
    elif change == "bet_raise":
        flags.update({"bet": True, "raise": True})
    elif change == "check_amount":
        flags.update(check=True, call=False)
        row.legal["call_delta"] = 1
    elif change == "call_zero":
        flags.update(check=False, call=True)
        row.legal["call_delta"] = 0
    elif change == "hero_folded":
        hero.folded = True
    elif change == "hero_undealt":
        hero.cards_dealt = False
    elif change == "hero_all_in":
        hero.all_in, hero.stack = True, 0
    elif change == "all_in_stack":
        hero.all_in, hero.stack = True, 1
    elif change == "folded_all_in":
        hero.folded, hero.all_in, hero.stack = True, True, 0
    errors = row.blocking_reasons()
    assert "big_blind_unknown_or_invalid" in errors
    assert expected in errors or f"player.{hero.seat}.{expected}" in errors
