from copy import deepcopy

import pytest

from poker.hud.models import PlayerObservation
from poker.hud.seat_occupancy import clear_empty_identities, filter_empty_players
from poker.hud.state import TableState


def player():
    return {
        "seat_index": 2,
        "name": "old",
        "is_active": None,
        "is_dealer": False,
        "stack": None,
        "current_bet": None,
    }


def empty():
    return {2: {"occupied": False, "confirmation_frames": [{"frame_id": 1}, {"frame_id": 2}]}}


def test_only_confirmed_empty_place_without_hand_participant_is_removed():
    payload = {"players": [player()]}
    before = deepcopy(payload)
    result, excluded = filter_empty_players(payload, empty(), {"participants": {}})
    assert result["players"] == []
    assert 2 in excluded
    assert payload == before
    for hand in [None, {"participants": {"2": {"fold_observed": True}}}]:
        assert filter_empty_players(payload, empty(), hand)[0] == payload
    assert filter_empty_players(payload, {}, {"participants": {}})[0] == payload


@pytest.mark.parametrize(
    "field,value",
    [("stack", 0), ("stack", 10), ("current_bet", 2), ("is_active", True), ("is_dealer", True)],
)
def test_conflicting_facts_keep_player(field, value):
    p = {**player(), field: value}
    assert filter_empty_players({"players": [p]}, empty(), {"participants": {}})[0]["players"] == [
        p
    ]


def test_new_occupant_does_not_inherit_name_after_empty_place():
    state = TableState()
    old = PlayerObservation((100, 100, 100, 40), "old", 95, "100", "recognized")
    for _ in range(2):
        state.update([old], (1000, 800))
    key = next(iter(state.seats))
    assert state.seats[key].name == "old"
    assert clear_empty_identities(state, [{"seat_index": 2, "roi": old.roi}], empty()) == [key]
    new = PlayerObservation(old.roi, "new", 95, "200", "recognized")
    state.update([new], (1000, 800))
    seat = next(iter(state.seats.values()))
    assert seat.key != key
    assert seat.name == ""
    state.update([new], (1000, 800))
    assert seat.name == "new"
