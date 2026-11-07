from datetime import UTC, datetime, timedelta

from poker.hud.hand_reconstruction import HandReconstructor


def row(number, *, hand="12345678", bet=None, board=(), action=None, backs=False):
    return {
        "frame_id": number,
        "captured_at": (datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=number)).isoformat(),
        "window": "table",
        "client_rect": [0, 0, 1400, 1130],
        "players": [],
        "context": {
            "hand_id": {"value": hand, "confidence": 95},
            "hero_visible": True,
            "decision_hand": {"board": list(board)},
            "table_signals": {
                "slots": [
                    {
                        "seat_index": i,
                        "roi": [i * 100, 200, 100, 40],
                        "current_bet": bet if i == 0 else None,
                        "card_back_evidence": {"present": True if backs and i == 0 else None},
                        "action_label": {"action": action, "words": [{"confidence": 95}]}
                        if action and i == 0
                        else None,
                    }
                    for i in range(7)
                ],
                "pot": {"value": None},
            },
        },
    }


def events(tracker, kind):
    return [e for h in tracker.hands.values() for e in h["events"] if e["kind"] == kind]


def test_all_in_caption_remains_unclassified_observation():
    tracker = HandReconstructor()
    for n in (1, 2, 3):
        tracker.update(row(n, action="all_in", backs=True))
    assert [e["action"] for e in events(tracker, "action_label")] == ["all_in"]
    assert tracker.current["verified_for_statistics"] is False
    assert not tracker.current["participants"]["0"]["fold_observed"]


def test_action_caption_does_not_hide_independent_repeated_card_evidence():
    from poker.hud.seat_evidence import participation

    tracker = HandReconstructor()
    for n in (1, 2):
        tracker.update(row(n, action="call", backs=True))
    assert participation(tracker) == {}
    tracker.update(row(3, action="call", backs=True))
    facts = participation(tracker)[0]
    assert facts["cards_dealt"] is True and facts["is_active"] is True
    evidence = {e["kind"]: e for e in facts["evidence"]}
    assert set(evidence) == {"action_label", "repeated_card_backs"}
    assert [s["frame_id"] for s in evidence["repeated_card_backs"]["confirmation_frames"]] == [2, 3]
    tracker.update(row(4, action="call", backs=True))
    assert len(participation(tracker)[0]["evidence"]) == 2
    assert len(events(tracker, "action_label")) == 1


def test_amount_changes_are_not_actions_and_missing_is_not_zero():
    tracker = HandReconstructor()
    for n in range(1, 5):
        tracker.update(row(n, bet=2))
    for n in (5, 6):
        tracker.update(row(n, bet=6))
    tracker.update(row(7))
    for n in (8, 9):
        tracker.update(row(n, bet=6))
    amounts = events(tracker, "bet_amount")
    assert [e["value"] for e in amounts] == [2, 6, 6]
    assert [e["observed_delta"] for e in amounts] == [None, 4, None]
    assert [s["frame_id"] for s in amounts[0]["confirmation_frames"]] == [3, 4]
    assert amounts[1]["previous_source"]["frame_id"] == 4
    assert not events(tracker, "action_label")


def test_membership_needs_repeated_backs_and_missing_does_not_fold():
    tracker = HandReconstructor()
    tracker.update(row(1, backs=True))
    tracker.update(row(2, backs=True))
    assert not tracker.hands["12345678"]["participants"]
    tracker.update(row(3, backs=True))
    tracker.update(row(4))
    participant = tracker.hands["12345678"]["participants"]["0"]
    assert participant["evidence"][0]["kind"] == "repeated_card_backs"
    assert not participant["fold_observed"]


def test_hero_participation_requires_two_valid_card_observations():
    tracker = HandReconstructor()
    for n in (1, 2, 3):
        item = row(n)
        item["context"]["decision_hand"].update(hero=["As", "Kd"], valid=True)
        tracker.update(item)
    hero = tracker.hands["12345678"]["participants"]["6"]
    assert hero["evidence"][0]["kind"] == "repeated_hero_cards"
    assert [s["frame_id"] for s in hero["evidence"][0]["confirmation_frames"]] == [2, 3]


def test_street_confirmation_does_not_duplicate_continuous_action_label():
    tracker = HandReconstructor()
    for n in (1, 2, 3, 4):
        tracker.update(row(n, action="check"))
    assert len(events(tracker, "action_label")) == 1


def test_street_confirmation_requires_same_cards_not_just_same_count():
    tracker = HandReconstructor()
    for n in (1, 2, 3):
        tracker.update(row(n))
    tracker.update(row(4, board=("Ah", "2c", "3s"), bet=5))
    tracker.update(row(5, board=("Ah", "2c", "8s"), bet=5))
    assert tracker.street is None
    assert [e["street"] for e in events(tracker, "street_observed")] == ["preflop"]
    assert not events(tracker, "bet_amount")
    tracker.update(row(6, board=("Ah", "2c", "8s"), bet=5))
    transition = events(tracker, "street_observed")[-1]
    assert transition["board_cards"] == ["Ah", "2c", "8s"]
    assert [f["frame_id"] for f in transition["confirmation_frames"]] == [5, 6]
    assert transition["previous_street"] == "preflop"
    assert transition["previous_street_source"]["frame_id"] == 3
    assert transition["previous_street_final_verified"] is False
    assert not events(tracker, "bet_amount")


def test_interruption_cannot_supply_previous_street_source():
    tracker = HandReconstructor()
    for n in (1, 2, 3):
        tracker.update(row(n))
    tracker.interrupt("capture_boundary")
    for n in (4, 5, 6):
        tracker.update(row(n, board=("Ah", "2c", "3s")))
    transition = events(tracker, "street_observed")[-1]
    assert transition["previous_street"] is None
    assert transition["previous_street_source"] is None
    assert [f["frame_id"] for f in transition["confirmation_frames"]] == [5, 6]


def test_unsampled_actions_are_not_mistaken_for_disappeared_labels():
    tracker = HandReconstructor()
    for n in (1, 2, 3):
        tracker.update(row(n, action="check"))
    intermediate = row(4)
    intermediate["context"]["table_signals"]["slots"][0]["action_sampled"] = False
    tracker.update(intermediate)
    tracker.update(row(5, action="check"))
    assert len(events(tracker, "action_label")) == 1


def test_sparse_pot_readings_expire_even_with_intermediate_bet_frames():
    tracker = HandReconstructor()
    for n in range(1, 22):
        item = row(n)
        signals = item["context"]["table_signals"]
        signals["pot"] = {"value": 2 if n < 20 else 5}
        signals["pot_sampled"] = n <= 4 or n >= 20
        tracker.update(item)
    assert [e["value"] for e in events(tracker, "pot_amount")] == [2, 5]
    assert events(tracker, "pot_amount")[-1]["observed_delta"] is None


def test_duplicate_frame_gap_and_new_hand_never_bridge_bets():
    tracker = HandReconstructor()
    for n in range(1, 5):
        tracker.update(row(n, bet=2))
    tracker.update(row(5, bet=8))
    tracker.update(row(5, bet=8))
    assert len(events(tracker, "bet_amount")) == 1
    for n in range(30, 34):
        tracker.update(row(n, bet=8))
    assert events(tracker, "bet_amount")[-1]["previous"] is None
    for n in range(34, 38):
        tracker.update(row(n, hand="87654321", bet=1))
    assert events(tracker, "bet_amount")[-1]["previous"] is None


def test_fold_deduplication_contradiction_and_board_regression_are_explicit():
    tracker = HandReconstructor()
    for n in (1, 2, 3):
        tracker.update(row(n, board=("Ah", "2c", "3s")))
    tracker.update(row(4, board=("Ah", "2c", "3s"), action="fold"))
    tracker.update(row(5, board=("Ah", "2c", "3s"), action="fold"))
    tracker.update(row(6, board=("Ah", "2c", "3s"), action="call"))
    tracker.update(row(7, bet=0))
    tracker.update(row(8, bet=0))
    hand = tracker.hands["12345678"]
    assert [e["action"] for e in events(tracker, "action_label")] == ["fold", "call"]
    assert {"action_after_fold", "board_conflict"} <= set(hand["warnings"])
    assert not events(tracker, "bet_amount")
    assert hand["history_complete"] is False and hand["verified_for_statistics"] is False


def test_short_ocr_gap_merges_only_with_known_unchanged_bet():
    tracker = HandReconstructor()
    for n in range(1, 8):
        item = row(n, bet=2, action="raise" if n in (3, 4, 6, 7) else None)
        item["captured_at"] = (
            datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=n / 2)
        ).isoformat()
        tracker.update(item)
    labels = events(tracker, "action_label")
    assert len(labels) == 1
    assert labels[0]["resumed_observations"][0]["frame_id"] == 6


def test_short_gap_does_not_merge_changed_bet_or_unknown_amount():
    for new_bet in (4, None):
        tracker = HandReconstructor()
        for n in range(1, 8):
            item = row(
                n, bet=2 if n < 6 else new_bet, action="raise" if n in (3, 4, 6, 7) else None
            )
            item["captured_at"] = (
                datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=n / 2)
            ).isoformat()
            tracker.update(item)
        assert len(events(tracker, "action_label")) == 2


def test_blinds_need_repeated_evidence_and_are_not_voluntary_actions():
    tracker = HandReconstructor()
    for n in range(1, 5):
        item = row(n)
        item["context"]["table_signals"]["slots"][0]["blind_label"] = {
            "blind": "small_blind",
            "words": [{"confidence": 96}],
        }
        tracker.update(item)
    blind = events(tracker, "blind_label")
    assert len(blind) == 1
    assert [r["frame_id"] for r in blind[0]["confirmation_frames"]] == [2, 3]
    assert not events(tracker, "action_label")
    tracker.interrupt("capture_boundary")
    tracker.update(row(5))
    assert not tracker.blinds


def test_dealer_requires_two_samples_and_reports_conflict():
    tracker = HandReconstructor()
    for n in range(1, 8):
        item = row(n)
        if n != 3:
            item["context"]["table_signals"]["dealer_slot"] = 0 if n < 5 else 1
        tracker.update(item)
    assert [e["seat_index"] for e in events(tracker, "dealer_observed")] == [0, 1]
    assert "dealer_conflict" in tracker.hands["12345678"]["warnings"]


def test_changed_amount_inside_gap_prevents_merge_even_if_it_returns():
    tracker = HandReconstructor()
    for n in range(1, 8):
        item = row(n, bet=4 if n == 5 else 2, action="raise" if n in (3, 4, 6, 7) else None)
        item["captured_at"] = (
            datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=n / 2)
        ).isoformat()
        tracker.update(item)
    assert len(events(tracker, "action_label")) == 2


def test_fresh_tuple_cards_and_json_list_cards_reconstruct_identically():
    trackers = [HandReconstructor(), HandReconstructor()]
    for n in range(1, 7):
        for tracker, container in zip(trackers, (tuple, list), strict=True):
            item = row(n, bet=2, board=() if n < 4 else ("Ah", "2c", "3s"))
            item["context"]["decision_hand"]["board"] = container(
                item["context"]["decision_hand"]["board"]
            )
            tracker.update(item)
    assert trackers[0].hands == trackers[1].hands
    assert [e["street"] for e in events(trackers[0], "street_observed")] == ["preflop", "flop"]
    assert events(trackers[0], "bet_amount")
