from copy import deepcopy

import pytest

from poker.hud.contribution_reconciliation import reconcile_observations
from tests.hud.test_hand_reconstruction import row


def reading(n, stack, bet, **kwargs):
    result = row(n, bet=bet, **kwargs)
    result["context"]["stack_readings"] = {"0": {"value": stack}}
    return result


def sequence():
    return [reading(1, 100, 2), reading(2, 100, 2), reading(3, 98, 4), reading(4, 98, 4)]


def test_balance_is_endpoint_evidence_not_an_action_or_hand_total():
    rows = sequence()
    original = deepcopy(rows)
    result = reconcile_observations(rows)
    assert rows == original
    assert len(result["points"]) == 2
    (interval,) = result["intervals"]
    assert interval["stack_decrease"] == interval["street_bet_increase"] == 200
    assert interval["residual"] == 0
    assert interval["contributed_delta"] is None
    assert interval["hand_contribution"] is None
    assert interval["history_complete"] is False
    assert interval["missing_intermediate_readings"] is False


def test_mismatch_is_not_repaired_and_return_is_only_a_candidate():
    rows = sequence()
    for r in rows[2:]:
        r["context"]["stack_readings"]["0"]["value"] = 97
    (interval,) = reconcile_observations(rows)["intervals"]
    assert interval["status"] == "amount_mismatch"
    assert interval["residual"] == 100
    rows = [reading(1, 98, 4), reading(2, 98, 4), reading(3, 100, 2), reading(4, 100, 2)]
    (interval,) = reconcile_observations(rows)["intervals"]
    assert interval["status"] == "balanced_observed_endpoints"
    assert interval["possible_return_or_correction"] is True
    assert interval["contributed_delta"] is None


def test_missing_middle_readings_are_preserved_as_a_gap():
    rows = sequence()[:2] + [reading(3, None, None), reading(4, 98, 4), reading(5, 98, 4)]
    (interval,) = reconcile_observations(rows)["intervals"]
    assert interval["missing_intermediate_readings"] is True
    assert interval["before"]["confirmation_frames"][-1]["frame_id"] == 2
    assert interval["after"]["confirmation_frames"][-1]["frame_id"] == 5


@pytest.mark.parametrize("boundary", ["hand", "street", "window", "geometry", "epoch", "payout"])
def test_different_capture_or_street_cannot_be_reconciled(boundary):
    rows = sequence()
    for r in rows[2:]:
        if boundary == "hand":
            r["context"]["hand_id"]["value"] = "87654321"
        elif boundary == "street":
            r["context"]["decision_hand"]["board"] = ["Ah", "2c", "3s"]
        elif boundary == "window":
            r["window"] = "other"
        elif boundary == "geometry":
            r["client_rect"] = [1, 0, 1400, 1130]
        elif boundary == "epoch":
            r["evidence_epoch"] = 2
        else:
            r["context"]["table_signals"]["slots"][1]["settlement_label"] = {"value": 10}
    assert reconcile_observations(rows)["intervals"] == []


def test_duplicate_out_of_order_or_single_amount_is_not_a_confirmed_endpoint():
    rows = sequence()
    assert reconcile_observations(rows[:3])["intervals"] == []
    assert reconcile_observations(rows[:2] + [rows[2], rows[2]])["intervals"] == []
    assert reconcile_observations(rows[:2] + [rows[3], rows[2]])["intervals"] == []


def test_pause_and_long_gap_reset_prior_endpoint():
    rows = sequence()
    assert not reconcile_observations(rows[:2] + [{"kind": "pause"}] + rows[2:])["intervals"]
    rows = rows[:2] + [reading(30, 98, 4), reading(31, 98, 4)]
    assert not reconcile_observations(rows)["intervals"]


def test_table_pot_growth_is_not_attributed_to_one_player():
    rows = sequence()
    for r, pot in zip(rows, (10, 10, 20, 20), strict=True):
        r["context"]["table_signals"]["pot"] = {"value": pot}
    (interval,) = reconcile_observations(rows)["intervals"]
    assert interval["before"]["pot"] == 1000
    assert interval["after"]["pot"] == 2000
    assert interval["stack_decrease"] == 200
    assert interval["residual"] == 0
    rows[3]["context"]["table_signals"]["pot"]["value"] = 21
    (interval,) = reconcile_observations(rows)["intervals"]
    assert interval["after"]["pot"] is None
