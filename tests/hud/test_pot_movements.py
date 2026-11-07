from copy import deepcopy

import pytest

from poker.hud.pot_movements import pot_movements
from tests.hud.test_hand_reconstruction import row


def sample(n, value):
    result = row(n)
    result["context"]["table_signals"]["pot"] = {"value": value}
    return result


def test_repeated_decrease_keeps_fold_context_without_inventing_return():
    rows = [sample(n, p) for n, p in enumerate((89.26, 89.26, 64.26, 64.26), 1)]
    rows[2]["context"]["table_signals"]["slots"][6]["action_label"] = {"action": "fold"}
    original = deepcopy(rows)
    (move,) = pot_movements(rows)
    assert rows == original
    assert move["delta"] == -2500
    assert move["direction"] == "decrease"
    assert any(s["folds"] == [6] for s in move["context_frames"])
    assert move["returned_amount"] is None and move["award"] is None and move["rake"] is None


def test_transient_amount_is_not_an_extra_bank_movement():
    rows = [sample(n, p) for n, p in enumerate((65.36, 65.36, 64.36, 64.26, 64.26), 1)]
    (move,) = pot_movements(rows)
    assert move["delta"] == -110
    assert move["after"]["value"] == 6426


def test_repeated_animation_values_are_observations_not_final_settlement():
    rows = [sample(n, p) for n, p in enumerate((14.29, 14.29, 16.09, 16.09, 16.07, 16.07), 1)]
    moves = pot_movements(rows)
    assert [m["delta"] for m in moves] == [180, -2]
    assert all(m["cause"] == "unclassified" and m["rake"] is None for m in moves)
    assert all(not m["verified_for_training"] for m in moves)


@pytest.mark.parametrize("change", ["hand", "window", "epoch", "pause", "duplicate"])
def test_boundaries_do_not_bridge_pots(change):
    rows = [sample(n, p) for n, p in enumerate((10, 10, 8, 8), 1)]
    if change == "pause":
        rows.insert(2, {"kind": "pause"})
    elif change == "duplicate":
        rows[-1] = deepcopy(rows[-2])
    else:
        for r in rows[2:]:
            if change == "hand":
                r["context"]["hand_id"]["value"] = "87654321"
            elif change == "window":
                r["window"] = "another"
            else:
                r["evidence_epoch"] = 2
    assert pot_movements(rows) == []
