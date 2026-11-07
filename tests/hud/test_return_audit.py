import json
from copy import deepcopy
from pathlib import Path

import pytest

from poker.hud.return_audit import audit_returns
from tests.hud.test_hand_reconstruction import row


def samples():
    rows = [row(n) for n in range(1, 5)]
    for n, source in enumerate(rows):
        source["context"]["stack_readings"] = {"0": {"value": 100 if n < 2 else 108}}
        source["context"]["table_signals"]["pot"] = {"value": 20 if n < 2 else 12}
        slots = source["context"]["table_signals"]["slots"]
        slots[0]["current_bet"] = 10 if n < 2 else None
        slots[1]["current_bet"] = 2 if n < 2 else None
        if n >= 2:
            slots[1]["action_label"] = {"action": "fold", "words": [{"confidence": 95}]}
    return rows


def test_repeated_stack_gain_and_opposing_folds_form_only_a_return_hypothesis():
    rows = samples()
    original = deepcopy(rows)
    (result,) = audit_returns(rows)
    assert rows == original
    assert result["candidate_return"] == result["observed_stack_increase"] == 800
    assert result["unknown_other_bet_seats"] == [2, 3, 4, 5, 6]
    assert result["repeated_visible_bets"] == [1000, 200, None, None, None, None, None]
    assert result["opposing_fold_seats"] == [1]
    assert result["returned_amount"] is None and result["payout"] is None and result["rake"] is None
    assert not result["verified_for_training"] and not result["verified_for_statistics"]


@pytest.mark.parametrize("pot", [None, 20, 21, 13])
def test_stack_increase_alone_cannot_explain_a_return(pot):
    rows = samples()
    for source in rows[2:]:
        source["context"]["table_signals"]["pot"]["value"] = pot
    assert audit_returns(rows) == []


@pytest.mark.parametrize(
    "case",
    [
        "payout",
        "pause",
        "window",
        "hand",
        "epoch",
        "gap",
        "duplicate",
        "one_stack_read",
        "one_fold",
        "weak_fold",
        "bet_conflict",
        "unknown_opposing_bet",
        "gain_mismatch",
        "winner_action",
        "pot_only",
    ],
)
def test_missing_or_conflicting_evidence_does_not_produce_return(case):
    rows = samples()
    if case == "pause":
        rows.insert(2, {"kind": "pause"})
    elif case == "duplicate":
        rows[-1] = deepcopy(rows[-2])
    elif case == "one_stack_read":
        rows[-1]["context"]["stack_readings"]["0"]["value"] = None
    elif case == "one_fold":
        rows[-1]["context"]["table_signals"]["slots"][1]["action_label"] = None
    elif case == "weak_fold":
        rows[-1]["context"]["table_signals"]["slots"][1]["action_label"]["words"][0][
            "confidence"
        ] = 84
    elif case == "bet_conflict":
        rows[1]["context"]["table_signals"]["slots"][0]["current_bet"] = 12
    elif case == "unknown_opposing_bet":
        for source in rows[:2]:
            source["context"]["table_signals"]["slots"][1]["current_bet"] = None
    else:
        for n, source in enumerate(rows[2:], 8):
            if case == "payout":
                source["context"]["table_signals"]["slots"][0]["settlement_label"] = {
                    "text": "wins"
                }
            elif case == "window":
                source["window"] = "other"
            elif case == "hand":
                source["context"]["hand_id"]["value"] = "87654321"
            elif case == "epoch":
                source["evidence_epoch"] = 2
            elif case == "gap":
                source["captured_at"] = row(n)["captured_at"]
            elif case == "winner_action":
                source["context"]["table_signals"]["slots"][0]["action_label"] = {"action": "call"}
            else:
                source["context"]["stack_readings"]["0"]["value"] = (
                    109 if case == "gain_mismatch" else 100
                )
                source["context"]["table_signals"]["pot"] = {"value": 2}
    assert audit_returns(rows) == []


@pytest.mark.parametrize(
    "directory,expected",
    [
        ("client_history_2880027230/replay", [("2880027230", 1, 4214)]),
        ("dense_20261007_middle", []),
        ("dense_hand_2879914331", []),
    ],
)
def test_recorded_return_is_not_inferred_when_payout_hides_stack(directory, expected):
    name = "observations_after.jsonl" if directory.endswith("replay") else "observations.jsonl"
    path = Path("artifacts/advisor") / directory / name
    if not path.is_file():
        pytest.skip("Local recorded evidence unavailable")
    rows = [json.loads(s) for s in path.read_text(encoding="utf8").splitlines()]
    result = audit_returns(rows)
    assert [(r["hand_id"], r["seat"], r["candidate_return"]) for r in result] == expected
    if result:
        assert [s["frame_id"] for s in result[0]["after"]["confirmation_frames"]] == [1172, 1173]
        assert result[0]["accounted_street_bets"] == [0, 4414, 0, 0, 0, 0, 200]
        assert set(result[0]["earlier_street_fold_evidence"]) == {0, 2, 3, 4, 5}
        assert result[0]["unknown_accounted_bet_seats"] == []
        assert result[0]["opponent_coverage"] == "accounted_for"
