from copy import deepcopy
from datetime import datetime, timedelta

import pytest

from poker.hud.return_audit import audit_returns
from tests.hud.test_hand_reconstruction import row
from tests.hud.test_return_audit import samples


def prior_folds():
    history = [row(1), row(2)]
    for source in history:
        for slot in source["context"]["table_signals"]["slots"][2:]:
            slot["action_label"] = {"action": "fold", "words": [{"confidence": 95}]}
    current = samples()
    for n, source in enumerate(current, 3):
        source.update(frame_id=n, captured_at=row(n)["captured_at"])
        source["context"]["decision_hand"]["board"] = ["Ah", "2c", "3s", "4h", "5d"]
    return history + current


def test_prior_street_folds_account_for_zero_without_overwriting_missing_readings():
    rows = prior_folds()
    original = deepcopy(rows)
    (result,) = audit_returns(rows)
    assert rows == original
    assert result["repeated_visible_bets"] == [1000, 200, None, None, None, None, None]
    assert result["accounted_street_bets"] == [1000, 200, 0, 0, 0, 0, 0]
    assert result["unknown_accounted_bet_seats"] == []
    assert result["all_opponents_fold_observed"] is True
    assert result["opponent_coverage"] == "accounted_for"
    assert result["returned_amount"] is None and not result["verified_for_training"]
    assert result["earlier_street_fold_evidence"][2]["confirmation_frames"][1]["frame_id"] == 2


@pytest.mark.parametrize(
    "case",
    [
        "single",
        "same_street",
        "card_conflict",
        "missing_board",
        "board_regression",
        "later_action",
        "later_bet",
        "late_fold",
        "pause",
        "epoch",
    ],
)
def test_uncertain_fold_cannot_supply_zero(case):
    rows = prior_folds()
    if case == "single":
        rows[0]["context"]["table_signals"]["slots"][2]["action_label"] = None
    elif case == "missing_board":
        for source in rows[:2]:
            source["context"]["decision_hand"].pop("board")
    elif case == "board_regression":
        earlier = row(0, board=["Ah", "2c", "3s", "4h", "5d"])
        rows.insert(0, earlier)
    elif case in {"same_street", "card_conflict"}:
        for source in rows[:2]:
            source["context"]["decision_hand"]["board"] = (
                ["Ah", "2c", "3s", "4h", "5d"] if case == "same_street" else ["Kh", "2c", "3s"]
            )
    elif case == "later_action":
        rows[-1]["context"]["table_signals"]["slots"][2]["action_label"] = {"action": "call"}
    elif case == "later_bet":
        rows[-1]["context"]["table_signals"]["slots"][2]["current_bet"] = 1
    elif case == "late_fold":
        for source in rows[:2]:
            source["context"]["table_signals"]["slots"][2]["action_label"] = None
        for source in rows[-2:]:
            source["context"]["table_signals"]["slots"][2]["action_label"] = {
                "action": "fold",
                "words": [{"confidence": 95}],
            }
    elif case == "pause":
        rows.insert(2, {"kind": "pause"})
    else:
        for source in rows[2:]:
            source["evidence_epoch"] = 2
    (result,) = audit_returns(rows)
    assert result["accounted_street_bets"][2] is None
    assert 2 in result["unknown_accounted_bet_seats"]
    assert 2 not in result["earlier_street_fold_evidence"]
    assert result["opponent_coverage"] == "incomplete"


def test_positive_bet_on_intermediate_street_invalidates_prior_fold():
    rows = prior_folds()
    intervening = deepcopy(rows[1])
    intervening["frame_id"] = 20
    intervening["captured_at"] = (
        datetime.fromisoformat(rows[1]["captured_at"]) + timedelta(milliseconds=100)
    ).isoformat()
    intervening["context"]["decision_hand"]["board"] = ["Ah", "2c", "3s"]
    slot = intervening["context"]["table_signals"]["slots"][2]
    slot.update(action_label=None, current_bet=1)
    rows.insert(2, intervening)
    (result,) = audit_returns(rows)
    assert result["accounted_street_bets"][2] is None
    assert result["opponent_coverage"] == "incomplete"
