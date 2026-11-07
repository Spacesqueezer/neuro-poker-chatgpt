"""Explicit engine/HUD mappings into the same offline contract."""

from copy import deepcopy

from poker.learning.advisor_contract import ACTIONS, AdvisorObservation, AdvisorPlayer, minor_units


def engine_card(card):
    suits = {"♣": "c", "♦": "d", "♥": "h", "♠": "s"}
    if not card or card[-1] not in suits:
        raise ValueError(f"Unsupported engine card: {card}")
    return ("T" if card[:-1] == "10" else card[:-1]) + suits[card[-1]]


def from_engine(
    state, legal, *, hand_id, observation_id, big_blind, history_complete=False, quantum="1"
):
    """Public state only. Public player order is the engine's table order."""
    seats = {p.name: i for i, p in enumerate(state.players)}
    if len(seats) != len(state.players):
        raise ValueError("Public player names must be unique")

    def amount(value):
        return minor_units(value, quantum)

    actions = {a: any(item.value == a for item in legal.actions) for a in ACTIONS}
    return AdvisorObservation(
        source="engine",
        hand_id=str(hand_id),
        observation_id=str(observation_id),
        captured_at=None,
        quantum=str(quantum),
        big_blind=amount(big_blind),
        hero_seat=seats[state.acting_player],
        dealer_seat=seats[state.dealer],
        clockwise_seats=list(range(len(state.players))),
        is_my_turn=True,
        street=state.street,
        hero_cards=[engine_card(c) for c in state.hole_cards],
        board=[engine_card(c) for c in state.board],
        pot=amount(state.pot),
        players=[
            AdvisorPlayer(
                seat=i,
                name=p.name,
                stack=amount(p.chips),
                street_contribution=amount(p.current_bet),
                hand_contribution=amount(p.total_contribution),
                cards_dealt=True,
                folded=p.folded,
                all_in=p.chips == 0 and not p.folded,
                position=p.position,
            )
            for i, p in enumerate(state.players)
        ],
        legal=dict(
            actions=actions,
            call_delta=amount(legal.call_amount),
            bet_to_min=amount(legal.min_bet),
            bet_to_max=amount(legal.max_bet),
            raise_to_min=amount(legal.min_raise_to),
            raise_to_max=amount(legal.max_raise_to),
        ),
        history=[
            dict(
                street=e.street,
                seat=seats[e.player],
                action=e.action,
                contributed_delta=amount(e.contributed),
                street_to=amount(e.bet_after),
                pot_after=amount(e.pot),
                target_after=amount(e.target),
            )
            for e in state.action_history
        ],
        history_complete=history_complete,
        source_blockers=[]
        if getattr(state, "hand_variant", "standard") == "standard"
        else ["hand_variant_unsupported"],
        evidence={
            "authority": "public_engine_state",
            "confidence": None,
            **(
                {"hand_variant": state.hand_variant, "forced_ante": amount(state.forced_ante)}
                if getattr(state, "hand_variant", "standard") != "standard"
                else {}
            ),
        },
    )


def from_hud(
    request,
    *,
    hand_id,
    observation_id,
    captured_at,
    hero_seat=6,
    quantum="0.01",
    big_blind=None,
    clockwise_seats=None,
    blockers=(),
    evidence=None,
):
    """Keep absent history/contributions unknown; inactive is not equivalent to folded."""

    def amount(value):
        return minor_units(value, quantum)

    flags = {a: request.get("can_" + a) for a in ACTIONS}
    dealers = [p["seat_index"] for p in request.get("players", []) if p.get("is_dealer") is True]
    return AdvisorObservation(
        source="hud",
        hand_id=str(hand_id or ""),
        observation_id=str(observation_id or ""),
        captured_at=captured_at,
        quantum=str(quantum),
        big_blind=amount(big_blind),
        hero_seat=hero_seat,
        dealer_seat=dealers[0] if len(dealers) == 1 else None,
        clockwise_seats=deepcopy(clockwise_seats),
        is_my_turn=request.get("is_my_turn"),
        street=request.get("street_name"),
        hero_cards=list(request.get("hero_hole_cards") or []),
        board=list(request.get("board_cards") or []),
        pot=amount(request.get("total_pot")),
        players=[
            AdvisorPlayer(
                seat=p["seat_index"],
                name=p.get("name") or None,
                stack=amount(p.get("stack")),
                street_contribution=amount(p.get("current_bet")),
                hand_contribution=None,
                cards_dealt=p.get("cards_dealt"),
                folded=None,
                all_in=None,
            )
            for p in request.get("players", [])
        ],
        legal=dict(
            actions=flags,
            call_delta=amount(request.get("call_amount_needed")),
            bet_to_min=amount(request.get("min_raise_amount")) if flags["bet"] is True else None,
            bet_to_max=amount(request.get("max_raise_amount")) if flags["bet"] is True else None,
            raise_to_min=amount(request.get("min_raise_amount"))
            if flags["raise"] is True
            else None,
            raise_to_max=amount(request.get("max_raise_amount"))
            if flags["raise"] is True
            else None,
        ),
        history=[],
        history_complete=False,
        source_blockers=sorted(set(blockers) | {"hud_state_reconstruction_unverified"}),
        evidence=deepcopy(evidence or {}),
    )
