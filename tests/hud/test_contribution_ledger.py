from copy import deepcopy

from poker.hud.contribution_ledger import contribution_coverage


def amount(value, street="preflop", delta=None, frame=1):
    return dict(
        seat=0,
        street=street,
        visible_total=value,
        delta_since_previous_reading=delta,
        evidence={"frame_id": frame},
    )


def test_last_observed_is_not_final_and_street_maxima_are_not_added():
    amounts = [
        amount(200),
        amount(400, delta=200, frame=2),
        amount(100, delta=-300, frame=3),
        amount(300, "flop", frame=4),
    ]
    original = deepcopy(amounts)
    result = contribution_coverage(amounts, [0, 1], "flop")
    player = result["players"][0]
    preflop, flop = player["streets"]
    assert preflop["last_observed_total"] == 100
    assert "visible_amount_decreased" in preflop["blockers"]
    assert preflop["decrease_sources"] == [{"frame_id": 3}]
    assert "street_final_unverified" in preflop["blockers"]
    assert flop["last_observed_total"] == 300
    assert all(s["final_total"] is None for s in player["streets"])
    assert player["hand_contribution"] is None
    assert amounts == original
    preflop["last_observed_source"]["frame_id"] = 99
    assert amounts == original


def test_missing_streets_and_unknown_seats_are_not_zero():
    result = contribution_coverage([amount(300, "turn")], [0, 1], "turn")
    assert [s["street"] for s in result["players"][0]["streets"]] == ["preflop", "flop", "turn"]
    for street in result["players"][1]["streets"]:
        assert street["last_observed_total"] is None
        assert "no_confirmed_amount" in street["blockers"]
    assert result["players"][0]["streets"][0]["last_observed_total"] is None


def test_explicit_zero_retained_but_does_not_prove_full_contribution():
    result = contribution_coverage([amount(0)], [], "preflop", ["gap_in_observations"])
    player = result["players"][0]
    assert player["streets"][0]["last_observed_total"] == 0
    assert "no_confirmed_amount" not in player["streets"][0]["blockers"]
    assert "hand_fragment_warnings" in player["streets"][0]["blockers"]
    assert player["hand_contribution"] is None
    assert result["verified_for_statistics"] is False
