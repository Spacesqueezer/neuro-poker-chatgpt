from copy import deepcopy

import pytest

from poker.hud.blind_audit import audit_blinds


def check(values, ids=(1, 2)):
    sources = [{"frame_id": i, "captured_at": f"2026-10-07T10:00:0{i}+00:00"} for i in ids]
    hands = [
        {
            "hand_id": "12345678",
            "events": [
                {
                    "kind": "blind_label",
                    "blind": "big_blind",
                    "seat_index": 0,
                    "confirmation_frames": sources,
                    "street": None,
                }
            ],
        }
    ]
    rows = [
        {
            **source,
            "window": "table",
            "client_rect": [0, 0, 1200, 900],
            "context": {
                "hand_id": {"value": "12345678", "confidence": 95},
                "decision_hand": {"board": []},
                "table_signals": {
                    "slots": [
                        {
                            "seat_index": 0,
                            "current_bet": value,
                            "blind_label": {"blind": "big_blind", "words": [{"confidence": 95}]},
                        }
                    ]
                },
            },
        }
        for source, value in zip(sources, values, strict=True)
    ]
    return hands, rows


def test_same_frame_amounts_do_not_require_inventing_street():
    hands, rows = check([2, 2])
    result = audit_blinds(hands, rows)[0]
    assert result["visible_amount"] == 2
    assert result["street"] is None
    assert result["verified_for_statistics"] is False


def test_unknown_conflict_and_duplicate_frames_are_not_confirmed():
    for values, ids, expected in [
        ([2, None], (1, 2), "amount_unknown"),
        ([2, 4], (1, 2), "amount_conflict"),
        ([2, 2], (1, 1), "amount_unknown"),
    ]:
        assert audit_blinds(*check(values, ids))[0]["status"] == expected


def test_wrong_hand_and_voluntary_action_cannot_prove_blind_amount():
    for field in ("hand", "action"):
        hands, rows = check([2, 2])
        if field == "hand":
            rows[0]["context"]["hand_id"]["value"] = "87654321"
        else:
            rows[0]["context"]["table_signals"]["slots"][0]["action_label"] = {"action": "raise"}
        assert audit_blinds(hands, rows)[0]["visible_amount"] is None


@pytest.mark.parametrize(
    "change", ["weak", "payout", "board", "window", "rect", "gap", "duplicate"]
)
def test_ambiguous_or_discontinuous_pairs_cannot_confirm_amount(change):
    hands, rows = check([2, 2])
    slot = rows[1]["context"]["table_signals"]["slots"][0]
    if change == "weak":
        slot["blind_label"]["words"][0]["confidence"] = 70
    elif change == "payout":
        slot["settlement_label"] = {"phase": "pot_awarded"}
    elif change == "board":
        rows[1]["context"]["decision_hand"]["board"] = ["Ah", "2c", "3s"]
    elif change == "window":
        rows[1]["window"] = "other"
    elif change == "rect":
        rows[1]["client_rect"] = [1, 0, 1200, 900]
    elif change == "gap":
        rows[1]["captured_at"] = "2026-10-07T10:00:09+00:00"
        hands[0]["events"][0]["confirmation_frames"][1]["captured_at"] = rows[1]["captured_at"]
    else:
        rows.append(rows[0])
    assert audit_blinds(hands, rows)[0]["visible_amount"] is None


def test_two_observed_big_blinds_do_not_become_one_assumed_position():
    hands, rows = check([2, 2])
    event = deepcopy(hands[0]["events"][0])
    event["seat_index"] = 1
    hands[0]["events"].append(event)
    for row in rows:
        slots = row["context"]["table_signals"]["slots"]
        slots.append({**deepcopy(slots[0]), "seat_index": 1})
    result = audit_blinds(hands, rows)
    assert [r["visible_amount"] for r in result] == [2, 2]
    assert all(r["hand_warnings"] == ["multiple_big_blind_amounts_observed"] for r in result)
    assert all(r["verified_for_statistics"] is False for r in result)
