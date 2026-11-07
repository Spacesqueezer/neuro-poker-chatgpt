from copy import deepcopy

import pytest

from tools.audit_hud_requests import matched_controls, unknown_fields


def source():
    return {
        "frame_id": 42,
        "captured_at": "2026-09-11T01:02:03+00:00",
        "image": "E:/session/00000042.jpg",
        "window": 1234,
        "client_rect": [100, 200, 1200, 1000],
    }


@pytest.mark.parametrize(
    "key,value",
    [
        ("frame_id", 43),
        ("captured_at", "2026-09-11T01:02:04+00:00"),
        ("image", "E:/other-session/00000042.jpg"),
        ("window", 4321),
        ("client_rect", [100, 200, 1200, 900]),
    ],
)
def test_join_rejects_cross_frame_time_and_session(key, value):
    row = source()
    control = deepcopy(row)
    control[key] = value
    assert not matched_controls(row, control)
    assert matched_controls(row, row)


def test_unknown_fields_identify_seats_without_rejecting_empty_names():
    assert unknown_fields(
        {
            "total_pot": None,
            "players": [{"seat_index": 3, "name": "", "stack": None, "current_bet": 0}],
        }
    ) == ["total_pot", "players[seat=3].stack"]


def test_missing_dealer_in_unaligned_slot_remains_unknown():
    from poker.hud.decision_stream import proposal, request_errors
    from poker.hud.hand import HandObservation

    request = proposal(
        HandObservation(hero=("Ah", "Ks"), my_turn=True),
        [],
        {"table_signals": {"slots": [{"seat_index": 0, "roi": [0, 0, 100, 40]}]}},
    )
    assert request["players"][0]["is_dealer"] is None
    assert "dealer_unknown" in request_errors(request)
