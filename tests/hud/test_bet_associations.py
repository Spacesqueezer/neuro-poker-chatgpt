from poker.hud.bet_associations import associate_bets


def amount(at="2026-01-01T00:00:10+00:00", seat=2, street="flop"):
    return {
        "kind": "bet_amount",
        "captured_at": at,
        "seat_index": seat,
        "street": street,
        "value": 16,
        "frame_id": 10,
    }


def action(at="2026-01-01T00:00:11+00:00", seat=2, street="flop"):
    return {
        "kind": "action_label",
        "captured_at": at,
        "seat_index": seat,
        "street": street,
        "action": "raise",
        "frame_id": 11,
    }


def links(events):
    return associate_bets([{"hand_id": "123", "events": events}])


def test_unique_label_remains_unverified_and_future_evidence_is_marked():
    result = links([amount(), action()])[0]
    assert result["status"] == "unique_candidate"
    assert result["uses_later_evidence"] is True
    assert result["verified_for_statistics"] is False
    assert result["amount_semantics"] == "visible_total_not_action_size"


def test_other_seat_street_or_distant_time_never_matches():
    result = links(
        [amount(), action(seat=3), action(street="turn"), action(at="2026-01-01T00:00:20+00:00")]
    )[0]
    assert result["status"] == "unmatched"


def test_multiple_amounts_cannot_share_a_unique_action():
    result = links([amount(), amount(at="2026-01-01T00:00:12+00:00"), action()])
    assert all(r["status"] == "ambiguous" for r in result)


def test_amount_after_action_has_its_own_confirmation_delay():
    result = links([action(at="2026-01-01T00:00:09+00:00"), amount()])[0]
    assert result["confirmation_timing"]["capture_span_after_action_ms"] == 1000
    assert result["confirmation_timing"]["uses_evidence_after_action"] is True
    # Legacy flag is relative to the amount, not to the action.
    assert result["uses_later_evidence"] is False


def test_street_confirmation_cannot_be_backdated_to_caption():
    caption = action(at="2026-01-01T00:00:09+00:00")
    caption["street_confirmation_frames"] = [
        {"captured_at": "2026-01-01T00:00:09+00:00"},
        {"captured_at": "2026-01-01T00:00:12+00:00"},
    ]
    result = links([caption, amount()])[0]
    assert result["confirmation_timing"] == {
        "last_evidence_captured_at": "2026-01-01T00:00:12+00:00",
        "capture_span_after_action_ms": 3000,
        "uses_evidence_after_action": True,
        "processing_latency_ms": None,
    }
    assert result["uses_later_evidence"] is True


def test_multiple_caption_candidates_have_no_single_action_delay():
    result = links([amount(), action(), action(at="2026-01-01T00:00:12+00:00")])[0]
    assert result["status"] == "ambiguous"
    assert result["confirmation_timing"]["capture_span_after_action_ms"] is None


def test_late_amount_confirmation_is_included_even_without_a_caption():
    observed = amount()
    observed["confirmation_frames"] = [
        {"captured_at": "2026-01-01T00:00:09+00:00"},
        {"captured_at": "2026-01-01T00:00:12+00:00"},
    ]
    result = links([observed])[0]
    assert result["status"] == "unmatched"
    assert result["uses_later_evidence"] is True
    timing = result["confirmation_timing"]
    assert timing["last_evidence_captured_at"] == "2026-01-01T00:00:12+00:00"
    assert timing["capture_span_after_action_ms"] is None
    assert timing["uses_evidence_after_action"] is None


def test_before_caption_context_does_not_compete_with_post_caption_observation():
    old = amount()
    new = amount(at="2026-01-01T00:00:12+00:00")
    new["confirmation_frames"] = [action(), new.copy()]
    before, after = links([old, new, action()])
    assert before["status"] == after["status"] == "ambiguous"
    assert before["candidate_capture_relations"] == ["before_caption"]
    assert before["post_caption_status"] == "none"
    assert after["candidate_capture_relations"] == ["at_or_after_caption"]
    assert after["post_caption_status"] == "unique_candidate"
    assert after["capture_order_proves_action_amount"] is False
    assert after["verified_for_statistics"] is False


def test_straddling_pair_is_not_a_post_caption_observation():
    observed = amount(at="2026-01-01T00:00:12+00:00")
    observed["confirmation_frames"] = [amount(), observed.copy()]
    result = links([observed, action()])[0]
    assert result["candidate_capture_relations"] == ["straddles_caption"]
    assert result["post_caption_status"] == "none"


def test_two_post_caption_amounts_remain_ambiguous():
    results = links(
        [action(), amount(at="2026-01-01T00:00:12+00:00"), amount(at="2026-01-01T00:00:13+00:00")]
    )
    assert all(r["post_caption_status"] == "ambiguous" for r in results)


def test_empty_confirmation_list_falls_back_to_observation():
    observed = amount()
    observed["confirmation_frames"] = []
    result = links([observed, action()])[0]
    assert result["candidate_capture_relations"] == ["before_caption"]
