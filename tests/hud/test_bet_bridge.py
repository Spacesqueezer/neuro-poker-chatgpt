from copy import deepcopy

import pytest

from poker.hud.bet_bridge import BetBridge
from tests.hud.test_confirmed_bets import row


def sample(number):
    item = row(number)
    item["evidence_epoch"] = 1
    return item


def setup():
    bridge = BetBridge()
    old = sample(2)
    confirmed = {
        "hand_id": "12345678",
        "bet_confirmations": {
            0: {
                "value": 2,
                "street": "preflop",
                "confirmation_frames": [{"frame_id": 1}, {"frame_id": 2}],
            }
        },
    }
    bridge.add(old, old["context"], confirmed)
    current = sample(3)
    evidence = {"hand_id": "12345678", "bet_confirmations": {}}
    return bridge, current, evidence


def test_bridge_requires_current_reading_and_preserves_three_sources():
    bridge, current, evidence = setup()
    result = bridge.augment(current, current["context"], evidence)
    assert not evidence["bet_confirmations"]
    fact = result["bet_confirmations"][0]
    assert fact["value"] == 2
    assert [r["frame_id"] for r in fact["confirmation_frames"]] == [1, 2, 3]


@pytest.mark.parametrize(
    "change",
    [
        "future",
        "stale",
        "epoch",
        "window",
        "hand",
        "board",
        "amount",
        "missing",
        "settlement",
        "roi",
        "duplicate",
    ],
)
def test_bridge_rejects_incompatible_or_unknown_current_frame(change):
    bridge, current, evidence = setup()
    slot = current["context"]["table_signals"]["slots"][0]
    if change == "future":
        current = sample(1)
    elif change == "stale":
        current = sample(6)
    elif change == "epoch":
        current["evidence_epoch"] = 2
    elif change == "window":
        current["window"] = "other"
    elif change == "hand":
        current["context"]["hand_id"]["value"] = "98765432"
    elif change == "board":
        current["context"]["decision_hand"]["board"] = ["Ah", "Kd", "2s"]
    elif change == "amount":
        slot["current_bet"] = 3
    elif change == "missing":
        slot["current_bet"] = None
    elif change == "settlement":
        slot["settlement_label"] = {"phase": "pot_awarded"}
    elif change == "roi":
        slot["roi"][0] += 10
    else:
        current["frame_id"] = 2
    assert not bridge.augment(current, current["context"], evidence)["bet_confirmations"]


def test_nearest_unknown_fast_frame_blocks_older_confirmation():
    bridge, current, evidence = setup()
    unknown = sample(3)
    bridge.add(unknown, unknown["context"], deepcopy(evidence))
    current = sample(4)
    assert not bridge.augment(current, current["context"], evidence)["bet_confirmations"]


def participant_setup():
    bridge, current, evidence = setup()
    current["context"]["decision_hand"].update(valid=True, hero=["Ah", "Kd"])
    previous = bridge.rows[-1]
    previous["context"]["decision_hand"].update(valid=True, hero=["Ah", "Kd"])
    current["context"]["table_signals"]["slots"][1]["card_back_evidence"] = {"present": True}
    previous["evidence"]["participation_evidence"] = {
        1: {"cards_dealt": True, "is_active": True, "evidence": [{"kind": "repeated_card_backs"}]}
    }
    return bridge, current, evidence


def test_bridge_adds_active_participant_only_with_current_visible_cards():
    bridge, current, evidence = participant_setup()
    result = bridge.augment(current, current["context"], evidence)
    assert result["participation_evidence"][1]["is_active"] is True
    assert result["participation_evidence"][1]["current_frame"]["frame_id"] == 3
    assert result["hand_participants"] == ["1"]
    assert "participation_evidence" not in evidence


@pytest.mark.parametrize(
    "change",
    [
        "fold",
        "hidden",
        "old_fold",
        "current_conflict",
        "known_action",
        "other_cards",
        "other_board",
        "window",
        "id",
        "duplicate",
    ],
)
def test_bridge_never_restores_player_across_conflicting_participation(change):
    bridge, current, evidence = participant_setup()
    slot = current["context"]["table_signals"]["slots"][1]
    if change == "fold":
        slot["action_label"] = {"action": "fold"}
    elif change == "hidden":
        slot["card_back_evidence"] = {"present": None}
    elif change == "old_fold":
        bridge.rows[-1]["evidence"]["participation_evidence"][1]["is_active"] = False
    elif change == "current_conflict":
        evidence["participation_evidence"] = {1: {"cards_dealt": True, "is_active": None}}
    elif change == "known_action":
        evidence["hand_participants"] = ["1"]
    elif change == "other_cards":
        current["context"]["decision_hand"]["hero"] = ["As", "Ks"]
    elif change == "other_board":
        current["context"]["decision_hand"]["board"] = ["2s", "3d", "4c"]
    elif change == "window":
        current["window"] = "other"
    elif change == "id":
        current["context"]["hand_id"]["confidence"] = 70
    else:
        current["frame_id"] = 2
    before = deepcopy(evidence.get("participation_evidence", {}))
    assert (
        bridge.augment(current, current["context"], evidence).get("participation_evidence", {})
        == before
    )


def test_same_capture_does_not_hide_previous_independent_proof():
    bridge, current, evidence = participant_setup()
    bridge.add(current, current["context"], {"hand_id": "12345678", "bet_confirmations": {}})
    result = bridge.augment(current, current["context"], evidence)
    assert [s["frame_id"] for s in result["bet_confirmations"][0]["confirmation_frames"]] == [
        1,
        2,
        3,
    ]
    assert result["participation_evidence"][1]["is_active"] is True


@pytest.mark.parametrize("change", ["amount", "hand", "cards", "fold", "time", "weak_id", "backs"])
def test_same_capture_conflict_prevents_older_proof(change):
    bridge, current, evidence = participant_setup()
    duplicate = deepcopy(current)
    c = duplicate["context"]
    if change == "amount":
        c["table_signals"]["slots"][0]["current_bet"] = 4
    elif change == "hand":
        c["hand_id"]["value"] = "87654321"
    elif change == "cards":
        c["decision_hand"]["hero"] = ["Ac", "Ks"]
    elif change == "fold":
        c["table_signals"]["slots"][1]["action_label"] = {"action": "fold"}
    elif change == "time":
        duplicate["captured_at"] = sample(2)["captured_at"]
    elif change == "weak_id":
        c["hand_id"]["confidence"] = 20
    else:
        c["table_signals"]["slots"][1]["card_back_evidence"] = {"present": None}
    bridge.add(duplicate, c, {"hand_id": "12345678", "bet_confirmations": {}})
    assert bridge.augment(current, current["context"], evidence) == evidence
