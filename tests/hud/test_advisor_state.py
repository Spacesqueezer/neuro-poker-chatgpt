from copy import deepcopy

import pytest

from poker.hud.advisor_state import attach_hand_fragment, build_advisor_draft
from poker.hud.hand_reconstruction import HandReconstructor
from poker.learning.advisor_adapters import from_hud
from tests.hud.test_hand_reconstruction import row


def setup(*, fold=False, stack=10):
    tracker = HandReconstructor()
    for n in range(1, 5):
        source = row(n, bet=2, backs=True, action="fold" if fold and n == 4 else None)
        tracker.update(source)
    request = dict(
        is_my_turn=True,
        street_name="preflop",
        hero_hole_cards=["Ah", "Kd"],
        board_cards=[],
        total_pot=3,
        call_amount_needed=1,
        players=[dict(seat_index=0, name="x", stack=stack, current_bet=2, cards_dealt=None)],
    )
    observation = from_hud(
        request, hand_id="12345678", observation_id="4", captured_at=source["captured_at"]
    )
    facts = dict(
        hand_id="12345678",
        stack_confirmations={
            0: dict(
                value=stack,
                confirmation_frames=[
                    {k: row(n).get(k) for k in ("frame_id", "captured_at", "image")} for n in (3, 4)
                ],
            )
        },
    )
    return observation, tracker, source, facts


def test_observed_fold_and_amounts_do_not_fabricate_hand_total_or_action_size():
    obs, tracker, source, facts = setup(fold=True)
    result = attach_hand_fragment(obs, tracker, source, facts)
    assert result.players[0].cards_dealt is True
    assert result.players[0].folded is True
    assert result.players[0].all_in is False
    assert result.players[0].hand_contribution is None
    assert result.history[0]["action"] == "fold"
    assert result.history[0]["contributed_delta"] is None
    assert result.history[0]["verified"] is False
    assert result.history_complete is False
    assert result.evidence["hand_fragment"]["observed_contributions"][0]["visible_total"] == 200
    coverage = result.evidence["hand_fragment"]["contribution_coverage"]
    assert coverage["players"][0]["streets"][0]["last_observed_total"] == 200
    assert coverage["players"][0]["hand_contribution"] is None
    assert obs.players[0].folded is None


@pytest.mark.parametrize("stack,expected", [(0, True), (10, False)])
def test_allin_uses_current_confirmed_stack_and_cards(stack, expected):
    obs, tracker, source, facts = setup(stack=stack)
    result = attach_hand_fragment(obs, tracker, source, facts)
    assert result.players[0].folded is False
    assert result.players[0].all_in is expected


@pytest.mark.parametrize(
    "change",
    ["duplicate", "future", "mismatch", "other_hand", "payout", "same_time", "wrong_last_time"],
)
def test_bad_stack_evidence_never_supplies_allin(change):
    obs, tracker, source, facts = setup(stack=0)
    f = facts["stack_confirmations"][0]
    if change == "duplicate":
        f["confirmation_frames"][0] = deepcopy(f["confirmation_frames"][1])
    elif change == "future":
        f["confirmation_frames"][0]["captured_at"] = row(5)["captured_at"]
    elif change == "mismatch":
        f["value"] = 1
    elif change == "other_hand":
        facts["hand_id"] = "87654321"
    elif change == "payout":
        source["context"]["table_signals"]["slots"][0]["settlement_label"] = {"value": 5}
    elif change == "same_time":
        f["confirmation_frames"][0]["captured_at"] = source["captured_at"]
    elif change == "wrong_last_time":
        f["confirmation_frames"][-1]["captured_at"] = row(3)["captured_at"]
    assert attach_hand_fragment(obs, tracker, source, facts).players[0].all_in is None


@pytest.mark.parametrize("change", ["future", "hand", "geometry", "street"])
def test_reconstruction_requires_matching_current_capture(change):
    obs, tracker, source, facts = setup()
    if change == "future":
        tracker.update(row(5, bet=2, backs=True))
    elif change == "hand":
        obs.hand_id = "87654321"
    elif change == "geometry":
        source["client_rect"] = [1, 2, 3, 4]
    elif change == "street":
        obs.street = "flop"
    result = attach_hand_fragment(obs, tracker, source, facts)
    assert "hand_fragment_source_mismatch" in result.source_blockers
    assert result.players[0].folded is None


@pytest.mark.parametrize(
    "field", ["confirmation_frames", "street_confirmation_frames", "previous_source"]
)
def test_nested_future_confirmation_rejects_fragment(field):
    obs, tracker, source, facts = setup(fold=True)
    future = {"frame_id": 5, "captured_at": row(5)["captured_at"]}
    event = tracker.current["events"][-1]
    event[field] = future if field == "previous_source" else [future]
    result = attach_hand_fragment(obs, tracker, source, facts)
    assert "hand_fragment_contains_future" in result.source_blockers
    assert "hand_fragment" not in result.evidence
    assert result.players[0].folded is None


def test_same_capture_with_different_epoch_rejects_fragment():
    obs, tracker, source, facts = setup()
    source = deepcopy(source)
    source["evidence_epoch"] = 99
    result = attach_hand_fragment(obs, tracker, source, facts)
    assert "hand_fragment_source_mismatch" in result.source_blockers


def test_live_epoch_is_preserved_and_matching_fragment_is_accepted():
    obs, tracker, source, facts = setup()
    for n in (5, 6):
        source = row(n, bet=2, backs=True)
        source["evidence_epoch"] = 7
        tracker.update(source)
    obs.captured_at = source["captured_at"]
    assert tracker.source["evidence_epoch"] == 7
    result = attach_hand_fragment(obs, tracker, source, {})
    assert "hand_fragment" in result.evidence
    assert "hand_fragment_source_mismatch" not in result.source_blockers


def test_future_participation_proof_does_not_bypass_event_cutoff():
    obs, tracker, source, facts = setup()
    participant = tracker.current["participants"]["0"]
    participant["evidence"].append({"kind": "repeated_card_backs", "confirmation_frames": [row(5)]})
    result = attach_hand_fragment(obs, tracker, source, facts)
    assert "hand_fragment_contains_future" in result.source_blockers
    assert result.players[0].cards_dealt is None


def test_missing_bet_is_not_zero_and_decrease_is_not_fold():
    obs, tracker, source, facts = setup()
    for n, bet in ((5, 4), (6, 4), (7, 1), (8, 1), (9, None)):
        source = row(n, bet=bet, backs=True)
        tracker.update(source)
    obs.captured_at = source["captured_at"]
    result = attach_hand_fragment(obs, tracker, source, {})
    amounts = result.evidence["hand_fragment"]["observed_contributions"]
    assert [a["visible_total"] for a in amounts] == [200, 400, 100]
    assert amounts[-1]["delta_since_previous_reading"] == -300
    assert result.players[0].folded is False
    assert result.players[0].hand_contribution is None
    assert not result.history


def test_street_transition_does_not_close_previous_contribution():
    obs, tracker, source, facts = setup()
    for n in (5, 6, 7):
        source = row(n, bet=3, board=["2c", "3h", "4d"], backs=True)
        tracker.update(source)
    obs.captured_at = source["captured_at"]
    obs.street = "flop"
    obs.board = ["2c", "3h", "4d"]
    result = attach_hand_fragment(obs, tracker, source, {})
    streets = result.evidence["hand_fragment"]["contribution_coverage"]["players"][0]["streets"]
    assert [s["last_observed_total"] for s in streets] == [200, 300]
    assert all(s["final_total"] is None for s in streets)
    assert "street_final_unverified" in streets[0]["blockers"]
    assert result.players[0].hand_contribution is None
    assert result.history_complete is False


def test_live_sidecar_is_always_diagnostic_and_bad_money_does_not_break_capture():
    obs, tracker, source, facts = setup()
    draft = dict(
        hand_id=obs.hand_id,
        blockers=["turn_continuity_unverified"],
        request={
            "is_my_turn": True,
            "hero_hole_cards": obs.hero_cards,
            "board_cards": [],
            "street_name": "preflop",
            "total_pot": 3,
            "players": [],
        },
    )
    result = build_advisor_draft(draft, tracker, source, source["context"], facts)
    assert result["would_send"] is False and result["model_called"] is False
    assert result["observation"]["schema_version"] == "advisor-observation/1"
    assert "turn_continuity_unverified" in result["blockers"]
    draft["request"]["total_pot"] = 1.001
    rejected = build_advisor_draft(draft, tracker, source, source["context"], facts)
    assert rejected["observation"] is None
    assert rejected["blockers"] == ["advisor_contract_build_failed"]
