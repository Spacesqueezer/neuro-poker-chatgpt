import json
from pathlib import Path

import pytest

from poker.hud.action_stack_audit import audit_action_stacks
from poker.hud.blind_audit import audit_blinds
from poker.hud.hand_reconstruction import HandReconstructor
from poker.hud.return_audit import audit_returns


def test_recorded_actions_agree_with_client_history_without_filling_missing_cards():
    root = Path("artifacts/advisor/client_history_2880027230")
    path = root / "replay/observations_after.jsonl"
    if not path.is_file() or not (root / "reference.json").is_file():
        pytest.skip("Local client history and replay unavailable")
    reference = json.loads((root / "reference.json").read_text(encoding="utf8"))
    tracker = HandReconstructor()
    for line in path.read_text(encoding="utf8").splitlines():
        source = json.loads(line)
        tracker.update(source)
        if source["frame_id"] == 1172:
            assert "" in source["context"]["decision_hand"]["board"]
            assert tracker.street is None
    hand = tracker.hands[reference["hand_id"]]
    # Physical slots verified on the same-session screenshot, not inferred from
    # the player-list order in the client history or from nickname OCR.
    names = ["aleks44py", "xolodrus", "riahka", "popovved", "blood1k", "maska19", "spacesqueezer"]
    labels = {"Fold": "fold", "Check": "check", "C": "call", "R": "raise", "B": "bet"}
    actual = [e for e in hand["events"] if e["kind"] == "action_label"]
    expected = [e for e in reference["actions"] if e["label"] in labels]
    assert len(actual) == len(expected) == 17
    matched = []
    for wanted in expected:
        candidates = [
            e
            for e in actual
            if names[e["seat_index"]] == wanted["player"]
            and e["action"] == labels[wanted["label"]]
            and e["street"] in (None, wanted["street"])
        ]
        assert len(candidates) == 1
        matched.append(candidates[0])
    assert len({e["frame_id"] for e in matched}) == 16  # Two actions share a capture.
    assert [e["frame_id"] for e in matched] == sorted(e["frame_id"] for e in matched)
    assert all(e["street"] is not None for e in actual)
    fold = next(e for e in actual if e["frame_id"] == 1172)
    assert fold["street_context"]["method"] == "compatible_partial_river"
    assert {
        (e["seat_index"], e["blind"]) for e in hand["events"] if e["kind"] == "blind_label"
    } == {(0, "small_blind"), (1, "big_blind")}
    assert hand["history_complete"] is False


def test_second_reference_boundary_frames_recover_blinds_without_cross_hand_return():
    root = Path("artifacts/advisor/client_history_2880026452")
    paths = [root / "observations_fresh_cards.jsonl", root / "boundaries/observations.jsonl"]
    if not all(path.is_file() for path in paths):
        pytest.skip("Local boundary replay unavailable")
    rows = {
        r["frame_id"]: r
        for path in paths
        for line in path.read_text(encoding="utf8").splitlines()
        for r in [json.loads(line)]
    }
    rows = sorted(rows.values(), key=lambda r: r["captured_at"])
    tracker = HandReconstructor()
    for row in rows:
        tracker.update(row)
    hand = tracker.hands["2880026452"]
    checks = audit_blinds([hand], rows)
    assert {(b["seat_index"], b["visible_amount"], b["status"]) for b in checks} == {
        (0, 2, "same_frame_amount_confirmed"),
        (2, 1, "same_frame_amount_confirmed"),
    }
    assert all(e["frame_id"] < 997 for e in hand["events"])
    assert not [r for r in audit_returns(rows) if r["hand_id"] == "2880026452"]
    assert hand["history_complete"] is False


def test_second_reference_confirms_raise_delta_and_eight_stack_changes():
    root = Path("artifacts/advisor/client_history_2880026452")
    path = root / "observations_fresh_cards.jsonl"
    if not path.is_file() or not (root / "reference.json").is_file():
        pytest.skip("Local second client history unavailable")
    reference = json.loads((root / "reference.json").read_text(encoding="utf8"))
    rows = [json.loads(s) for s in path.read_text(encoding="utf8").splitlines()]
    assert len(rows) == 173
    tracker = HandReconstructor()
    for source in rows:
        tracker.update(source)
    hand = tracker.hands[reference["hand_id"]]
    names = ["aleks44py", "xolodrus", "riahka", "popovved", "blood1k", "maska19", "spacesqueezer"]
    labels = {"Fold": "fold", "Check": "check", "C": "call", "R": "raise", "B": "bet"}
    actual = [e for e in hand["events"] if e["kind"] == "action_label"]
    expected = [e for e in reference["actions"] if e["label"] in labels]
    assert len(actual) == len(expected) == 15
    matched = []
    for wanted in expected:
        candidates = [
            e
            for e in actual
            if names[e["seat_index"]] == wanted["player"]
            and e["action"] == labels[wanted["label"]]
            and e["street"] == wanted["street"]
        ]
        assert len(candidates) == 1
        matched.append(candidates[0])
    frames = [e["frame_id"] for e in matched]
    assert frames == sorted(frames)
    assert len(set(frames)) == 14  # Two folds share a capture; exact ordering is unknown.
    results = audit_action_stacks(rows, [hand])
    assert [(r["action"]["frame_id"], r["stack_decrease"]) for r in results] == [
        (784, 400),
        (813, 600),
        (843, 400),
        (861, 804),
        (868, 804),
        (907, 1564),
        (914, 1564),
        (955, 3042),
    ]
    # R 6 is an additional six here, not a total bet of six.
    raise_event = next(e for e in reference["actions"] if e["order"] == 9)
    assert raise_event["amount_semantics"] == "paid_delta"
    assert 200 + raise_event["amount"] == 400 + 400 == 800
    assert reference["displayed_total_pot_by_street"]["preflop"] == 800 + 800 + 100
    assert hand["board_cards"] == reference["board_cards"]
    assert audit_returns(rows) == []  # Reference UB cannot supply hidden stack evidence.
    assert hand["history_complete"] is False


def test_third_reference_keeps_sitting_out_players_out_of_actions_and_matches_deltas():
    reference_path = Path("artifacts/advisor/client_history_2879914331/reference.json")
    replay = Path(
        "artifacts/advisor/refreshed_2879914331_20261012/20261012_075810_516261"
        "/session_20261005_035204_be9e45/observations.jsonl"
    )
    if not reference_path.is_file() or not replay.is_file():
        pytest.skip("Local third client history unavailable")
    reference = json.loads(reference_path.read_text(encoding="utf8"))
    rows = [json.loads(line) for line in replay.read_text(encoding="utf8").splitlines()]
    tracker = HandReconstructor()
    for row in rows:
        tracker.update(row)
    hand = tracker.hands[reference["hand_id"]]
    names = ["statham", "bm51", "dimaferoom", None, "lesnix", "xolodrus", "spacesqueezer"]
    sit_out = {p["name"] for p in reference["players"] if p["sitting_out"]}
    assert sit_out == {"statham", "xolodrus"}
    assert set(hand["participants"]) == {"1", "2", "4", "6"}
    labels = {"R": "raise", "C": "call", "B": "bet", "Fold": "fold"}
    actions = [e for e in hand["events"] if e["kind"] == "action_label"]
    expected = [e for e in reference["actions"] if e["label"] in labels]
    assert len(actions) == len(expected) == 12
    for e, wanted in zip(actions, expected, strict=True):
        assert names[e["seat_index"]] == wanted["player"]
        assert e["action"] == labels[wanted["label"]]
        assert e["street"] == wanted["street"]
        assert wanted["player"] not in sit_out
    stacks = audit_action_stacks(rows, [hand])
    assert [r["stack_decrease"] for r in stacks] == [400, 400, 1000, 700, 1000, 1000, 1000, 1000]
    # A partial board stays partial even though the independent history is known.
    obscured = next(r for r in rows if r["frame_id"] == 1357)
    assert obscured["context"]["decision_hand"]["board"] == ["Ac", "7s", "7c", ""]
    assert hand["board_cards"] == reference["board_cards"]
    assert not [r for r in audit_returns(rows) if r["hand_id"] == reference["hand_id"]]
    assert hand["history_complete"] is False


def test_third_reference_call_separates_prior_stake_from_post_caption_total():
    from artifacts.advisor.client_history_2879914331.verify import REPLAY
    from poker.hud.bet_associations import associate_bets

    if not REPLAY.is_file():
        pytest.skip("Local refreshed replay unavailable")
    tracker = HandReconstructor()
    for line in REPLAY.read_text(encoding="utf8").splitlines():
        tracker.update(json.loads(line))
    rows = associate_bets([tracker.hands["2879914331"]])
    call = [r for r in rows if any(a["frame_id"] == 1289 for a in r["action_candidates"])]
    assert len(call) == 2
    assert {(r["amount_observation"]["value"], r["post_caption_status"]) for r in call} == {
        (4.0, "none"),
        (11.0, "unique_candidate"),
    }
    assert all(r["status"] == "ambiguous" for r in call)
    assert all(r["verified_for_statistics"] is False for r in call)
